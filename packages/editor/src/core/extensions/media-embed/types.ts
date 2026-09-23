/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export enum IMediaEmbedAttributeNames {
  ID = "id",
  SRC = "src",
  MEDIA_TYPE = "media-type",
  ALT = "alt",
  CAPTION = "caption",
  BLOCK_TYPE = "data-block-type",
}

export type TMediaEmbedAttributes = {
  [IMediaEmbedAttributeNames.ID]: string | null;
  [IMediaEmbedAttributeNames.SRC]: string;
  [IMediaEmbedAttributeNames.MEDIA_TYPE]: "image" | "video";
  [IMediaEmbedAttributeNames.ALT]: string;
  [IMediaEmbedAttributeNames.CAPTION]: string;
  [IMediaEmbedAttributeNames.BLOCK_TYPE]: "media-embed-component";
};

export const DEFAULT_MEDIA_EMBED_ATTRIBUTES: TMediaEmbedAttributes = {
  [IMediaEmbedAttributeNames.ID]: null,
  [IMediaEmbedAttributeNames.SRC]: "",
  [IMediaEmbedAttributeNames.MEDIA_TYPE]: "image",
  [IMediaEmbedAttributeNames.ALT]: "",
  [IMediaEmbedAttributeNames.CAPTION]: "",
  [IMediaEmbedAttributeNames.BLOCK_TYPE]: "media-embed-component",
};

const ALLOWED_IMAGE_ORIGINS = [
  "https://images.unsplash.com",
  "https://i.imgur.com",
  "https://pbs.twimg.com",
  "https://cdn.discordapp.com",
  "https://*.githubusercontent.com",
  "https://upload.wikimedia.org",
];

const ALLOWED_VIDEO_ORIGINS = [
  "https://www.youtube.com",
  "https://youtu.be",
  "https://player.vimeo.com",
  "https://www.dailymotion.com",
];

const SAFE_PROTOCOLS = ["https:", "data:"];

export function isAllowedMediaOrigin(url: string, mediaType: "image" | "video"): boolean {
  try {
    const parsed = new URL(url);
    if (!SAFE_PROTOCOLS.includes(parsed.protocol)) return false;
    const origins = mediaType === "video" ? ALLOWED_VIDEO_ORIGINS : ALLOWED_IMAGE_ORIGINS;
    return origins.some((origin) => {
      if (origin.includes("*.")) {
        const pattern = origin.replace("*.", ".");
        return parsed.hostname.endsWith(pattern);
      }
      return parsed.origin === origin;
    });
  } catch {
    return false;
  }
}

export function detectMediaType(url: string): "image" | "video" {
  const videoExtensions = [".mp4", ".webm", ".ogg", ".mov", ".avi"];
  const lowerUrl = url.toLowerCase();
  if (videoExtensions.some((ext) => lowerUrl.includes(ext))) return "video";
  if (lowerUrl.includes("youtube.com") || lowerUrl.includes("youtu.be")) return "video";
  if (lowerUrl.includes("vimeo.com")) return "video";
  if (lowerUrl.includes("dailymotion.com")) return "video";
  return "image";
}

export function extractVideoEmbedUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("youtube.com") && parsed.searchParams.has("v")) {
      return `https://www.youtube.com/embed/${parsed.searchParams.get("v")}`;
    }
    if (parsed.hostname === "youtu.be") {
      return `https://www.youtube.com/embed${parsed.pathname}`;
    }
    if (parsed.hostname.includes("youtube.com") && parsed.pathname.includes("/embed/")) {
      return url;
    }
    if (parsed.hostname.includes("vimeo.com")) {
      const match = parsed.pathname.match(/\/(\d+)/);
      if (match) return `https://player.vimeo.com/video/${match[1]}`;
    }
    return null;
  } catch {
    return null;
  }
}
