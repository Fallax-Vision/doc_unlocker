package com.fallaxvision.docunlocker.engine;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.HashSet;
import java.util.Set;

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
    private final int sectorCount;
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
        if (data.length < 512 || data.length > 16 * 1024 * 1024
                || !java.util.Arrays.equals(java.util.Arrays.copyOf(data, 8),
                new byte[]{(byte) 0xd0, (byte) 0xcf, 0x11, (byte) 0xe0,
                        (byte) 0xa1, (byte) 0xb1, 0x1a, (byte) 0xe1})) {
            throw new IOException("Not an OLE compound file");
        }
        int major = u16(26);
        if (u16(28) != 0xfffe || !((major == 3 && u16(30) == 9)
                || (major == 4 && u16(30) == 12)) || u16(32) != 6) {
            throw new IOException("Unsupported OLE sector format");
        }
        sectorSize = 1 << u16(30);
        miniSectorSize = 1 << u16(32);
        if (data.length % sectorSize != 0) throw new IOException("Truncated OLE sector");
        sectorCount = data.length / sectorSize - 1;
        int numDifat = u32(72);
        int firstDifat = u32(68);
        int firstDir = u32(48);
        miniCutoff = u32(56);
        int firstMiniFat = u32(60);
        int numMiniFat = u32(64);
        int entriesPerSec = sectorSize / 4;
        int numFat = u32(44);
        if (miniCutoff != 4096 || numDifat < 0 || numDifat > sectorCount
                || numMiniFat < 0 || numMiniFat > sectorCount
                || numFat < 1 || numFat > sectorCount) {
            throw new IOException("Invalid OLE allocation counts");
        }

        // Build the list of FAT sectors from the DIFAT (109 in header + chain).
        List<Integer> fatSectors = new ArrayList<>();
        Set<Integer> fatSeen = new HashSet<>();
        for (int i = 0; i < 109; i++) {
            int v = u32(76 + i * 4);
            if (v >= 0) addFatSector(v, fatSectors, fatSeen, numFat);
        }
        int difat = firstDifat;
        Set<Integer> difatSeen = new HashSet<>();
        for (int n = 0; n < numDifat; n++) {
            if (!difatSeen.add(difat)) throw new IOException("Cyclic DIFAT");
            int base = sectorOffset(difat);
            for (int i = 0; i < entriesPerSec - 1; i++) {
                int v = u32(base + i * 4);
                if (v >= 0) addFatSector(v, fatSectors, fatSeen, numFat);
            }
            difat = u32(base + (entriesPerSec - 1) * 4);
        }
        if (fatSectors.size() != numFat || (numDifat > 0 && difat != ENDOFCHAIN))
            throw new IOException("Invalid DIFAT length");

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
            if (chain.length != numMiniFat) throw new IOException("Invalid mini-FAT length");
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
            if (nameLen < 2 || nameLen > 64 || nameLen % 2 != 0)
                throw new IOException("Invalid directory name");
            Entry e = new Entry();
            e.type = type;
            e.name = nameLen > 2
                    ? new String(db, off, nameLen - 2, StandardCharsets.UTF_16LE) : "";
            e.start = u32From(db, off + 116);
            e.size = u64From(db, off + 120);
            if (e.size < 0 || e.size > data.length) throw new IOException("Invalid stream size");
            entries.add(e);
            if (type == 5) {
                if (miniStream.length != 0) throw new IOException("Duplicate root stream");
                miniStream = readBigChain(e.start, e.size);
            }
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

    private void addFatSector(int sector, List<Integer> list, Set<Integer> seen, int limit)
            throws IOException {
        sectorOffset(sector);
        if (!seen.add(sector) || list.size() >= limit) throw new IOException("Invalid FAT sector");
        list.add(sector);
    }

    private int[] followFat(int start) throws IOException {
        List<Integer> chain = new ArrayList<>();
        Set<Integer> seen = new HashSet<>();
        int s = start;
        while (s != ENDOFCHAIN) {
            sectorOffset(s);
            if (s >= fat.length || !seen.add(s) || chain.size() >= sectorCount)
                throw new IOException("Invalid or cyclic FAT chain");
            chain.add(s);
            s = fat[s];
        }
        int[] out = new int[chain.size()];
        for (int i = 0; i < out.length; i++) out[i] = chain.get(i);
        return out;
    }

    private byte[] readBigChain(int start, long size) throws IOException {
        if (size == 0) return new byte[0];
        if (size < 0 || size > data.length) throw new IOException("Invalid stream size");
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int[] chain = followFat(start);
        if (chain.length != (size + sectorSize - 1) / sectorSize)
            throw new IOException("Stream length does not match chain");
        for (int s : chain)
            out.write(data, sectorOffset(s), (int) Math.min(sectorSize, size - out.size()));
        return trim(out.toByteArray(), size);
    }

    private byte[] readMiniChain(int start, long size) throws IOException {
        if (size == 0) return new byte[0];
        if (size < 0 || size > miniStream.length) throw new IOException("Invalid mini stream size");
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int s = start;
        Set<Integer> seen = new HashSet<>();
        while (s != ENDOFCHAIN) {
            if (s < 0 || s >= miniFat.length || s >= miniStream.length / miniSectorSize
                    || !seen.add(s) || out.size() >= size)
                throw new IOException("Invalid or cyclic mini-FAT chain");
            int off = s * miniSectorSize;
            out.write(miniStream, off, (int) Math.min(miniSectorSize, size - out.size()));
            s = miniFat[s];
        }
        if (out.size() != size) throw new IOException("Truncated mini stream");
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

    private int sectorOffset(int sector) throws IOException {
        if (sector < 0 || sector >= sectorCount) throw new IOException("Sector out of range");
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
