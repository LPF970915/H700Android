package com.roc.h700;

import java.net.HttpURLConnection;
import java.net.URL;
import java.net.InetAddress;
import org.json.JSONArray;
import org.json.JSONObject;

/** Read-only connectivity diagnosis. Uses normal certificate verification. */
public final class NetworkEndpointProbe {
    public static void main(String[] urls) throws Exception {
        JSONArray results = new JSONArray();
        for (String value : urls) {
            JSONObject result = new JSONObject();
            result.put("url", value);
            long started = System.nanoTime();
            HttpURLConnection connection = null;
            try {
                URL url = new URL(value);
                JSONArray addresses = new JSONArray();
                for (InetAddress address : InetAddress.getAllByName(url.getHost())) {
                    addresses.put(address.getHostAddress());
                }
                result.put("addresses", addresses);
                connection = (HttpURLConnection) url.openConnection();
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(4000);
                connection.setReadTimeout(4000);
                connection.setRequestProperty("Connection", "close");
                result.put("status", connection.getResponseCode());
                result.put("content_length", connection.getContentLengthLong());
                result.put("location", connection.getHeaderField("Location"));
            } catch (Exception failure) {
                result.put("error", failure.toString());
            } finally {
                if (connection != null) connection.disconnect();
                result.put("elapsed_ms", (System.nanoTime() - started) / 1000000L);
                results.put(result);
            }
        }
        System.out.println(results.toString(2));
    }
}
