package com.fallaxvision.docunlocker.engine;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Microsoft Office 2013+ "agile" encryption (AES + SHA-512), per MS-OFFCRYPTO.
 * Verifies a password and decrypts the package. Pure JVM (javax.crypto +
 * MessageDigest) so it works identically on the desktop and on Android.
 */
public final class OfficeCrypto {

    // Block keys (MS-OFFCRYPTO 2.3.4.x).
    private static final byte[] BK_VERIFIER_INPUT =
            {(byte) 0xfe, (byte) 0xa7, (byte) 0xd2, 0x76, 0x3b, 0x4b, (byte) 0x9e, 0x79};
    private static final byte[] BK_VERIFIER_VALUE =
            {(byte) 0xd7, (byte) 0xaa, 0x0f, 0x6d, 0x30, 0x61, 0x34, 0x4e};
    private static final byte[] BK_KEY_VALUE =
            {0x14, 0x6e, 0x0b, (byte) 0xe7, (byte) 0xab, (byte) 0xac, (byte) 0xd0, (byte) 0xd6};

    private OfficeCrypto() {}

    /** Result of decrypting; null plaintext means the password was wrong. */
    public static final class Result {
        public final boolean ok;
        public final byte[] plaintext;
        Result(boolean ok, byte[] pt) { this.ok = ok; this.plaintext = pt; }
    }

    private static String attr(String xml, String name) {
        Matcher m = Pattern.compile(name + "=\"([^\"]*)\"").matcher(xml);
        return m.find() ? m.group(1) : null;
    }

    private static String element(String xml, String tagContains) {
        Matcher m = Pattern.compile("<[^>]*" + tagContains + "[^>]*>").matcher(xml);
        return m.find() ? m.group(0) : null;
    }

    private static byte[] b64(String s) { return Base64.getDecoder().decode(s); }

    private static byte[] sha512(byte[]... parts) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-512");
            for (byte[] p : parts) md.update(p);
            return md.digest();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    private static byte[] le32(int v) {
        return new byte[]{(byte) v, (byte) (v >> 8), (byte) (v >> 16), (byte) (v >> 24)};
    }

    private static byte[] fit(byte[] b, int len) {
        byte[] out = new byte[len];
        // pad with 0x36 (per spec) if too short, else truncate.
        java.util.Arrays.fill(out, (byte) 0x36);
        System.arraycopy(b, 0, out, 0, Math.min(b.length, len));
        return out;
    }

    private static byte[] aesCbcDecrypt(byte[] key, byte[] iv, byte[] data) throws Exception {
        Cipher c = Cipher.getInstance("AES/CBC/NoPadding");
        c.init(Cipher.DECRYPT_MODE, new SecretKeySpec(key, "AES"),
                new IvParameterSpec(iv));
        return c.doFinal(data);
    }

    private static byte[] deriveKey(byte[] hFinal, byte[] blockKey, int keyBytes) {
        return fit(sha512(hFinal, blockKey), keyBytes);
    }

    /**
     * Decrypt the document. Returns Result(ok, plaintext); ok=false (and null
     * plaintext) means the password was wrong. Throws only on malformed input.
     */
    public static Result decrypt(byte[] fileBytes, String password) throws Exception {
        Cfbf cfbf = new Cfbf(fileBytes);
        byte[] info = cfbf.read("EncryptionInfo");
        // 8-byte version header, then UTF-8 XML.
        String xml = new String(info, 8, info.length - 8, StandardCharsets.UTF_8);

        String keyData = element(xml, "keyData");
        String encKey = element(xml, "encryptedKey");
        if (keyData == null || encKey == null) {
            throw new IllegalStateException("Not agile-encrypted (no keyData/encryptedKey).");
        }

        int spin = Integer.parseInt(attr(encKey, "spinCount"));
        int keyBits = Integer.parseInt(attr(encKey, "keyBits"));
        int hashSize = Integer.parseInt(attr(encKey, "hashSize"));
        int blockSize = Integer.parseInt(attr(encKey, "blockSize"));
        byte[] pSalt = b64(attr(encKey, "saltValue"));
        byte[] encVerInput = b64(attr(encKey, "encryptedVerifierHashInput"));
        byte[] encVerValue = b64(attr(encKey, "encryptedVerifierHashValue"));
        byte[] encKeyValue = b64(attr(encKey, "encryptedKeyValue"));
        int keyBytes = keyBits / 8;

        // Password hash: H0 = SHA512(salt + UTF16LE(pw)); iterate spinCount.
        byte[] h = sha512(pSalt, password.getBytes(StandardCharsets.UTF_16LE));
        for (int i = 0; i < spin; i++) h = sha512(le32(i), h);

        // Verify the password.
        byte[] verInput = aesCbcDecrypt(deriveKey(h, BK_VERIFIER_INPUT, keyBytes),
                fit(pSalt, blockSize), encVerInput);
        byte[] verValue = aesCbcDecrypt(deriveKey(h, BK_VERIFIER_VALUE, keyBytes),
                fit(pSalt, blockSize), encVerValue);
        byte[] expect = sha512(verInput);
        boolean ok = true;
        for (int i = 0; i < hashSize && i < expect.length && i < verValue.length; i++) {
            if (expect[i] != verValue[i]) { ok = false; break; }
        }
        if (!ok) return new Result(false, null);

        // Recover the real package key.
        byte[] secretKey = aesCbcDecrypt(deriveKey(h, BK_KEY_VALUE, keyBytes),
                fit(pSalt, blockSize), encKeyValue);
        secretKey = java.util.Arrays.copyOf(secretKey, keyBytes);

        // Decrypt the package in 4096-byte segments.
        int kdBlockSize = Integer.parseInt(attr(keyData, "blockSize"));
        byte[] kdSalt = b64(attr(keyData, "saltValue"));
        byte[] pkg = cfbf.read("EncryptedPackage");
        long total = (pkg[0] & 0xffL) | ((pkg[1] & 0xffL) << 8) | ((pkg[2] & 0xffL) << 16)
                | ((pkg[3] & 0xffL) << 24) | ((pkg[4] & 0xffL) << 32) | ((pkg[5] & 0xffL) << 40)
                | ((pkg[6] & 0xffL) << 48) | ((pkg[7] & 0xffL) << 56);
        int seg = 4096;
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int pos = 8;
        int index = 0;
        while (pos < pkg.length) {
            int len = Math.min(seg, pkg.length - pos);
            // segment must be a multiple of the block size for CBC
            int blk = (len / kdBlockSize) * kdBlockSize;
            if (blk == 0) break;
            byte[] iv = fit(sha512(kdSalt, le32(index)), kdBlockSize);
            byte[] chunk = new byte[blk];
            System.arraycopy(pkg, pos, chunk, 0, blk);
            out.write(aesCbcDecrypt(secretKey, iv, chunk));
            pos += seg;
            index++;
        }
        byte[] all = out.toByteArray();
        if (total >= 0 && total < all.length) {
            all = java.util.Arrays.copyOf(all, (int) total);
        }
        return new Result(true, all);
    }
}
