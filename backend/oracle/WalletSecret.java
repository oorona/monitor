import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import oracle.security.pki.OracleWallet;
import oracle.security.pki.OracleSecretStore;

public final class WalletSecret {
    public static void main(String[] args) {
        char[] value = null;
        int status = 0;
        try {
            if (args.length != 2) throw new IllegalArgumentException();
            OracleWallet wallet = new OracleWallet();
            wallet.open(args[0] + "/cwallet.sso", null);
            OracleSecretStore store = wallet.getSecretStore();
            value = store.getSecret(args[1]);
            if (value == null || value.length == 0) throw new IllegalArgumentException();
            java.io.Writer output = new java.io.OutputStreamWriter(System.out, StandardCharsets.UTF_8);
            output.write(value);
            output.flush();
        } catch (Exception error) {
            System.err.println("Shared Oracle wallet entry unavailable");
            status = 2;
        } finally {
            if (value != null) Arrays.fill(value, '\0');
        }
        if (status != 0) System.exit(status);
    }
}
