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

function isExactOrSubdomain(hostname: string, domain: string): boolean {
  return hostname === domain || hostname.endsWith(`.${domain}`);
}

function isYoutubeHostname(hostname: string): boolean {
  return hostname === "youtu.be" || isExactOrSubdomain(hostname, "youtube.com");
}

function isVimeoHostname(hostname: string): boolean {
  return isExactOrSubdomain(hostname, "vimeo.com");
}

function isDailymotionHostname(hostname: string): boolean {
  return isExactOrSubdomain(hostname, "dailymotion.com");
}

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
  try {
    const parsed = new URL(url);
    if (
      isYoutubeHostname(parsed.hostname) ||
      isVimeoHostname(parsed.hostname) ||
      isDailymotionHostname(parsed.hostname)
    ) {
      return "video";
    }
  } catch {
    // Not a valid URL; fall through to image default.
  }
  return "image";
}

export function extractVideoEmbedUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (isYoutubeHostname(parsed.hostname) && parsed.searchParams.has("v")) {
      return `https://www.youtube.com/embed/${parsed.searchParams.get("v")}`;
    }
    if (parsed.hostname === "youtu.be") {
      return `https://www.youtube.com/embed${parsed.pathname}`;
    }
    if (isYoutubeHostname(parsed.hostname) && parsed.pathname.includes("/embed/")) {
      return url;
    }
    if (isVimeoHostname(parsed.hostname)) {
      const match = parsed.pathname.match(/\/(\d+)/);
      if (match) return `https://player.vimeo.com/video/${match[1]}`;
    }
    return null;
  } catch {
    return null;
  }
}
