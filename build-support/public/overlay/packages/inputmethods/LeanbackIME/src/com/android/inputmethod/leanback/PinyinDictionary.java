/* SPDX-License-Identifier: Apache-2.0 */
package com.android.inputmethod.leanback;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.GZIPInputStream;

/** Offline Pinyin lookup using the frequency-ranked AOSP word lexicon. */
public final class PinyinDictionary {
    public static final int MAX_INPUT = 40;

    public static final class Candidate {
        public final String text;
        public final int letters;

        private Candidate(String text, int letters) {
            this.text = text;
            this.letters = letters;
        }
    }

    private static final class Word {
        final String text;
        final double score;

        Word(String text, double frequency) {
            this.text = text;
            score = Math.log(frequency);
        }
    }

    private final Map<String, List<Word>> entries = new HashMap<>();
    private int maxSpelling;
    private double logTotalFrequency;

    public static PinyinDictionary load(InputStream compressed) throws IOException {
        PinyinDictionary dictionary = new PinyinDictionary();
        double frequencySum = 0;
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                new GZIPInputStream(compressed), StandardCharsets.UTF_8))) {
            String row;
            while ((row = reader.readLine()) != null) {
                String[] columns = row.split("\t", -1);
                if (columns.length != 3 || !columns[0].matches("[a-z]+") || columns[1].isEmpty()) {
                    throw new IOException("Invalid Pinyin lexicon row");
                }
                double frequency = Double.parseDouble(columns[2]);
                if (!Double.isFinite(frequency) || frequency <= 0) {
                    throw new IOException("Invalid Pinyin lexicon frequency");
                }
                dictionary.entries.computeIfAbsent(columns[0], key -> new ArrayList<>())
                        .add(new Word(columns[1], frequency));
                dictionary.maxSpelling = Math.max(dictionary.maxSpelling, columns[0].length());
                frequencySum += frequency;
            }
        } catch (NumberFormatException malformed) {
            throw new IOException("Invalid Pinyin lexicon frequency", malformed);
        }
        if (dictionary.entries.isEmpty()) throw new IOException("Empty Pinyin lexicon");
        dictionary.logTotalFrequency = Math.log(frequencySum);
        return dictionary;
    }

    private String bestSentence(String spelling) {
        int length = spelling.length();
        double[] scores = new double[length + 1];
        Arrays.fill(scores, Double.NEGATIVE_INFINITY);
        scores[length] = 0;
        String[] suffixes = new String[length + 1];
        suffixes[length] = "";
        for (int start = length - 1; start >= 0; start--) {
            for (int end = start + 1; end <= Math.min(length, start + maxSpelling); end++) {
                if (suffixes[end] == null) continue;
                List<Word> words = entries.get(spelling.substring(start, end));
                if (words == null) continue;
                Word best = words.get(0);
                double score = scores[end] + best.score - logTotalFrequency;
                if (score > scores[start]) {
                    scores[start] = score;
                    suffixes[start] = best.text + suffixes[end];
                }
            }
        }
        return suffixes[0];
    }

    public List<Candidate> candidates(String spelling) {
        if (spelling.isEmpty() || spelling.length() > MAX_INPUT) return new ArrayList<>();
        Map<String, Candidate> results = new LinkedHashMap<>();
        int length = spelling.length();
        List<Word> exact = entries.get(spelling);
        if (exact != null) {
            for (Word word : exact) results.put(word.text, new Candidate(word.text, length));
        }
        String composed = bestSentence(spelling);
        if (composed != null) results.putIfAbsent(composed, new Candidate(composed, length));
        for (int end = Math.min(length - 1, maxSpelling); end > 0; end--) {
            List<Word> prefix = entries.get(spelling.substring(0, end));
            if (prefix == null) continue;
            for (Word word : prefix) results.putIfAbsent(word.text, new Candidate(word.text, end));
        }
        return new ArrayList<>(results.values());
    }
}
