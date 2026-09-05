package com.fallaxvision.docunlocker.engine;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.concurrent.CancellationException;
import java.util.function.BooleanSupplier;

public final class DocumentInput {
    public static final int MAX_BYTES = 16 * 1024 * 1024;
    private DocumentInput() {}

    public static byte[] read(InputStream stream, BooleanSupplier cancelled) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        while (true) {
            if (cancelled.getAsBoolean()) throw new CancellationException("Stopped");
            int count = stream.read(buffer, 0, Math.min(buffer.length, MAX_BYTES - out.size() + 1));
            if (count < 0) return out.toByteArray();
            if (out.size() + count > MAX_BYTES)
                throw new IOException("Documents must be 16 MiB or smaller on Android.");
            out.write(buffer, 0, count);
        }
    }
}
