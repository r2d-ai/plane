/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { TPublishedPage } from "@plane/types";
// api service
import { APIService } from "../api.service";

/**
 * Service class for reading externally published Wiki pages from the space app.
 * Mirrors the project publish service but is served by the public page endpoint.
 * @extends {APIService}
 */
export class SitesPagePublishService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  /**
   * Retrieves the published page payload for a public anchor.
   * @param {string} anchor - The public token of the published page
   * @returns {Promise<TPublishedPage>}
   * @throws {Error} If the API request fails
   */
  async retrievePageByAnchor(anchor: string): Promise<TPublishedPage> {
    return this.get(`/api/public/anchor/${anchor}/page/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }
}
