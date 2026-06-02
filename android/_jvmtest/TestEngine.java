import com.fallaxvision.docunlocker.engine.OfficeCrypto;
import java.nio.file.*;

public class TestEngine {
    public static void main(String[] args) throws Exception {
        byte[] data = Files.readAllBytes(Paths.get(args[0]));
        for (int i = 1; i < args.length; i++) {
            String pw = args[i];
            OfficeCrypto.Result r = OfficeCrypto.decrypt(data, pw);
            String magic = "-";
            boolean pk = false;
            if (r.ok && r.plaintext != null) {
                int n = Math.min(4, r.plaintext.length);
                StringBuilder sb = new StringBuilder();
                for (int k = 0; k < n; k++) sb.append(String.format("%02x", r.plaintext[k]));
                magic = sb.toString();
                pk = r.plaintext.length > 1 && r.plaintext[0] == 'P' && r.plaintext[1] == 'K';
            }
            System.out.println("pw=" + pw + " ok=" + r.ok + " magic=" + magic
                    + " validZip=" + pk
                    + (r.plaintext != null ? " size=" + r.plaintext.length : ""));
        }
    }
}
