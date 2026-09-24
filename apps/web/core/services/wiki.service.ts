/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// types
import { API_BASE_URL } from "@plane/constants";
import type { TWikiPersonalPageResponse, TWikiPersonalSection, TWikiScope, TWikiSearchResponse } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export class WikiService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetchScopes(): Promise<TWikiScope[]> {
    return this.get("/api/wiki/scopes/")
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async search(query: string, limit: number): Promise<TWikiSearchResponse> {
    return this.get("/api/wiki/search/", { params: { query, limit } })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchPersonalPages(
    section: TWikiPersonalSection,
    query = "",
    cursor?: string
  ): Promise<TWikiPersonalPageResponse> {
    return this.get("/api/wiki/personal/", { params: { section, query, cursor } })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
