import com.fallaxvision.docunlocker.engine.*;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.concurrent.CancellationException;
import java.util.concurrent.atomic.AtomicInteger;

public final class SecurityTests {
    interface Checked { void run() throws Exception; }
    static void rejected(Checked run) throws Exception {
        try { run.run(); } catch (Exception expected) { return; }
        throw new AssertionError("Malformed input accepted");
    }
    static byte[] replace(byte[] data, String from, String to) {
        if (from.length() != to.length()) throw new AssertionError("Keep fixture length");
        byte[] out = data.clone();
        byte[] old = from.getBytes(StandardCharsets.UTF_8), next = to.getBytes(StandardCharsets.UTF_8);
        boolean found = false;
        for (int i = 0; i <= out.length - old.length; i++) {
            if (Arrays.equals(Arrays.copyOfRange(out, i, i + old.length), old)) {
                System.arraycopy(next, 0, out, i, next.length); found = true;
            }
        }
        if (!found) throw new AssertionError("Missing fixture metadata: " + from);
        return out;
    }
    static void integer(byte[] data, int offset, int value) {
        for (int i = 0; i < 4; i++) data[offset + i] = (byte) (value >>> (8 * i));
    }
    static int integer(byte[] data, int offset) {
        return java.nio.ByteBuffer.wrap(data, offset, 4).order(java.nio.ByteOrder.LITTLE_ENDIAN).getInt();
    }
    public static void main(String[] args) throws Exception {
        byte[] data = Files.readAllBytes(Paths.get(args[0]));
        OfficeCrypto.Prepared prepared = OfficeCrypto.prepare(data);
        if (prepared.decrypt("wrong", () -> false).ok) throw new AssertionError("Wrong password accepted");
        if (!prepared.decrypt("Crack3d!", () -> false).ok) throw new AssertionError("Valid password rejected");
        for (String[] pair : new String[][]{{"blockSize=\"16\"", "blockSize=\"99\""},
                {"hashSize=\"64\"", "hashSize=\"00\""}, {"keyBits=\"256\"", "keyBits=\"999\""},
                {"spinCount=\"100000\"", "spinCount=\"-00001\""}}) {
            rejected(() -> OfficeCrypto.prepare(replace(data, pair[0], pair[1])));
        }
        byte[] bad = data.clone(); integer(bad, 72, Integer.MAX_VALUE);
        rejected(() -> new Cfbf(bad));
        byte[] shift = data.clone(); shift[30] = 31;
        rejected(() -> new Cfbf(shift));
        byte[] cycle = data.clone();
        int fat = integer(cycle, 76), directory = integer(cycle, 48);
        integer(cycle, (fat + 1) * 512 + directory * 4, directory);
        rejected(() -> new Cfbf(cycle));
        AtomicInteger checks = new AtomicInteger();
        try {
            prepared.decrypt("wrong", () -> checks.incrementAndGet() >= 4);
            throw new AssertionError("Cancellation ignored");
        } catch (CancellationException expected) { }
        InputStream endless = new InputStream() {
            public int read() { return 0; }
            public int read(byte[] b, int off, int len) { Arrays.fill(b, off, off + len, (byte) 0); return len; }
        };
        rejected(() -> DocumentInput.read(endless, () -> false));
        if (!Arrays.equals(data, DocumentInput.read(new ByteArrayInputStream(data), () -> false)))
            throw new AssertionError("Import changed bytes");
        rejected(() -> DocumentInput.read(new ByteArrayInputStream(data), () -> true));
        System.out.println("PASS: valid/wrong password, metadata limits, CFBF chains, cancellation, bounded import");
    }
}
