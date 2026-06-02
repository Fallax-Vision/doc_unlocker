package com.fallaxvision.docunlocker.engine;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Minimal reader for the OLE / Compound File Binary Format (MS-CFB).
 * Just enough to pull named streams ("EncryptionInfo", "EncryptedPackage")
 * out of an encrypted Microsoft Office document. Pure JVM - no Android APIs -
 * so it can be unit-tested on the desktop.
 */
public final class Cfbf {

    private final byte[] data;
    private final int sectorSize;
    private final int miniSectorSize;
    private final int miniCutoff;
    private final int[] fat;
    private final int[] miniFat;
    private final List<Entry> entries = new ArrayList<>();
    private byte[] miniStream = new byte[0];

    private static final int ENDOFCHAIN = 0xFFFFFFFE;

    public static final class Entry {
        public String name;
        public int type;     // 1=storage 2=stream 5=root
        public int start;
        public long size;
    }

    public Cfbf(byte[] data) throws IOException {
        this.data = data;
        if (data.length < 512 || (data[0] & 0xff) != 0xD0 || (data[1] & 0xff) != 0xCF
                || (data[2] & 0xff) != 0x11 || (data[3] & 0xff) != 0xE0) {
            throw new IOException("Not an OLE compound file");
        }
        sectorSize = 1 << u16(30);
        miniSectorSize = 1 << u16(32);
        int numDifat = u32(72);
        int firstDifat = u32(68);
        int firstDir = u32(48);
        miniCutoff = u32(56);
        int firstMiniFat = u32(60);
        int numMiniFat = u32(64);
        int entriesPerSec = sectorSize / 4;

        // Build the list of FAT sectors from the DIFAT (109 in header + chain).
        List<Integer> fatSectors = new ArrayList<>();
        for (int i = 0; i < 109; i++) {
            int v = u32(76 + i * 4);
            if (v >= 0) fatSectors.add(v);
        }
        int difat = firstDifat;
        for (int n = 0; n < numDifat && difat >= 0; n++) {
            int base = sectorOffset(difat);
            for (int i = 0; i < entriesPerSec - 1; i++) {
                int v = u32(base + i * 4);
                if (v >= 0) fatSectors.add(v);
            }
            difat = u32(base + (entriesPerSec - 1) * 4);
        }

        // Read the FAT.
        fat = new int[fatSectors.size() * entriesPerSec];
        int idx = 0;
        for (int fs : fatSectors) {
            int base = sectorOffset(fs);
            for (int i = 0; i < entriesPerSec; i++) fat[idx++] = u32(base + i * 4);
        }

        // Read the mini-FAT.
        if (firstMiniFat >= 0 && numMiniFat > 0) {
            int[] chain = followFat(firstMiniFat);
            miniFat = new int[chain.length * entriesPerSec];
            int j = 0;
            for (int s : chain) {
                int base = sectorOffset(s);
                for (int i = 0; i < entriesPerSec; i++) miniFat[j++] = u32(base + i * 4);
            }
        } else {
            miniFat = new int[0];
        }

        // Read the directory and its entries.
        ByteArrayOutputStream dirBytes = new ByteArrayOutputStream();
        for (int s : followFat(firstDir)) dirBytes.write(data, sectorOffset(s), sectorSize);
        byte[] db = dirBytes.toByteArray();
        for (int off = 0; off + 128 <= db.length; off += 128) {
            int nameLen = (db[off + 64] & 0xff) | ((db[off + 65] & 0xff) << 8);
            int type = db[off + 66] & 0xff;
            if (type == 0) continue;
            Entry e = new Entry();
            e.type = type;
            e.name = nameLen > 2
                    ? new String(db, off, nameLen - 2, StandardCharsets.UTF_16LE) : "";
            e.start = u32From(db, off + 116);
            e.size = u64From(db, off + 120);
            entries.add(e);
            if (type == 5) miniStream = readBigChain(e.start, e.size);  // root -> mini container
        }
    }

    public boolean has(String name) {
        return find(name) != null;
    }

    public byte[] read(String name) throws IOException {
        Entry e = find(name);
        if (e == null) throw new IOException("Stream not found: " + name);
        if (e.size >= miniCutoff) return readBigChain(e.start, e.size);
        return readMiniChain(e.start, e.size);
    }

    private Entry find(String name) {
        for (Entry e : entries) if (name.equals(e.name)) return e;
        return null;
    }

    private int[] followFat(int start) {
        List<Integer> chain = new ArrayList<>();
        int s = start;
        int guard = 0;
        while (s >= 0 && s != ENDOFCHAIN && guard++ < fat.length + 1) {
            chain.add(s);
            s = (s < fat.length) ? fat[s] : ENDOFCHAIN;
        }
        int[] out = new int[chain.size()];
        for (int i = 0; i < out.length; i++) out[i] = chain.get(i);
        return out;
    }

    private byte[] readBigChain(int start, long size) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (int s : followFat(start)) out.write(data, sectorOffset(s), sectorSize);
        return trim(out.toByteArray(), size);
    }

    private byte[] readMiniChain(int start, long size) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int s = start;
        int guard = 0;
        while (s >= 0 && s != ENDOFCHAIN && guard++ < miniFat.length + 1) {
            int off = s * miniSectorSize;
            out.write(miniStream, off, Math.min(miniSectorSize, miniStream.length - off));
            s = (s < miniFat.length) ? miniFat[s] : ENDOFCHAIN;
        }
        return trim(out.toByteArray(), size);
    }

    private static byte[] trim(byte[] b, long size) {
        if (size >= 0 && size < b.length) {
            byte[] t = new byte[(int) size];
            System.arraycopy(b, 0, t, 0, (int) size);
            return t;
        }
        return b;
    }

    private int sectorOffset(int sector) {
        return (sector + 1) * sectorSize;
    }

    private int u16(int off) {
        return (data[off] & 0xff) | ((data[off + 1] & 0xff) << 8);
    }

    private int u32(int off) {
        return u32From(data, off);
    }

    private static int u32From(byte[] b, int off) {
        return (b[off] & 0xff) | ((b[off + 1] & 0xff) << 8)
                | ((b[off + 2] & 0xff) << 16) | ((b[off + 3] & 0xff) << 24);
    }

    private static long u64From(byte[] b, int off) {
        long lo = u32From(b, off) & 0xffffffffL;
        long hi = u32From(b, off + 4) & 0xffffffffL;
        return lo | (hi << 32);
    }
}
