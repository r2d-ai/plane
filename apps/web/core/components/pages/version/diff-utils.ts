/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Simple word-level diff for HTML content.
 * Returns an array of diff segments with type, old text, and new text.
 */

export type TDiffSegment = {
  type: "equal" | "added" | "removed" | "changed";
  oldText?: string;
  newText?: string;
};

/**
 * Splits text into words.
 */
function tokenize(text: string): string[] {
  return text.split(/\s+/).filter(Boolean);
}

/**
 * Computes a simple word-level diff between two HTML strings.
 * Returns segments marking what was added, removed, or changed.
 */
export function computeHtmlDiff(oldHtml: string, newHtml: string): TDiffSegment[] {
  if (!oldHtml && !newHtml) return [];
  if (!oldHtml) return [{ type: "added", newText: newHtml }];
  if (!newHtml) return [{ type: "removed", oldText: oldHtml }];

  const oldText = oldHtml
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const newText = newHtml
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (oldText === newText) return [{ type: "equal", oldText, newText }];

  const oldWords = tokenize(oldText);
  const newWords = tokenize(newText);

  // Simple LCS-based diff
  const lcs = longestCommonSubsequence(oldWords, newWords);
  const segments: TDiffSegment[] = [];
  let oldIdx = 0;
  let newIdx = 0;
  let lcsIdx = 0;

  while (oldIdx < oldWords.length || newIdx < newWords.length) {
    if (
      lcsIdx < lcs.length &&
      oldIdx < oldWords.length &&
      newIdx < newWords.length &&
      oldWords[oldIdx] === lcs[lcsIdx] &&
      newWords[newIdx] === lcs[lcsIdx]
    ) {
      segments.push({ type: "equal", oldText: oldWords[oldIdx], newText: newWords[newIdx] });
      oldIdx++;
      newIdx++;
      lcsIdx++;
    } else if (oldIdx < oldWords.length && (lcsIdx >= lcs.length || oldWords[oldIdx] !== lcs[lcsIdx])) {
      // Collect consecutive removed words
      let removed = oldWords[oldIdx];
      oldIdx++;
      while (oldIdx < oldWords.length && (lcsIdx >= lcs.length || oldWords[oldIdx] !== lcs[lcsIdx])) {
        removed += " " + oldWords[oldIdx];
        oldIdx++;
      }
      // Check if next new words are the replacement
      if (newIdx < newWords.length && (lcsIdx >= lcs.length || newWords[newIdx] !== lcs[lcsIdx])) {
        let added = newWords[newIdx];
        newIdx++;
        while (newIdx < newWords.length && (lcsIdx >= lcs.length || newWords[newIdx] !== lcs[lcsIdx])) {
          added += " " + newWords[newIdx];
          newIdx++;
        }
        segments.push({ type: "changed", oldText: removed, newText: added });
      } else {
        segments.push({ type: "removed", oldText: removed });
      }
    } else if (newIdx < newWords.length && (lcsIdx >= lcs.length || newWords[newIdx] !== lcs[lcsIdx])) {
      let added = newWords[newIdx];
      newIdx++;
      while (newIdx < newWords.length && (lcsIdx >= lcs.length || newWords[newIdx] !== lcs[lcsIdx])) {
        added += " " + newWords[newIdx];
        newIdx++;
      }
      segments.push({ type: "added", newText: added });
    } else {
      break;
    }
  }

  // If no segments were generated, fall back to showing both versions
  if (segments.length === 0) {
    return [
      { type: "removed", oldText: oldText },
      { type: "added", newText: newText },
    ];
  }

  return segments;
}

/**
 * Longest common subsequence for word-level diff.
 */
function longestCommonSubsequence(a: string[], b: string[]): string[] {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to find the LCS
  const result: string[] = [];
  let i = m;
  let j = n;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      result.unshift(a[i - 1]);
      i--;
      j--;
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--;
    } else {
      j--;
    }
  }

  return result;
}
