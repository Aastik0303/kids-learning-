import { apiClient } from "@/services/api/client";
import type { ChildProfile } from "@/types/domain";

export type ChildCreateInput = {
  sessionToken: string;
  name: string;
  ageGroup: string;
  age?: number | null;
  preferredLanguage?: string;
};

export type ChildUpdateInput = {
  sessionToken: string;
  name?: string;
  ageGroup?: string;
  age?: number;
  preferredLanguage?: string;
};

/** /children — see `backend/app/api/children.py`. */
export const childApi = {
  create(input: ChildCreateInput) {
    return apiClient.post<ChildProfile>("/children", {
      session_token: input.sessionToken,
      name: input.name,
      age_group: input.ageGroup,
      age: input.age ?? null,
      preferred_language: input.preferredLanguage ?? "English",
    });
  },

  /** Every child belonging to the signed-in parent. */
  list(sessionToken: string) {
    return apiClient.get<ChildProfile[]>("/children", { sessionToken });
  },

  get(childId: string) {
    return apiClient.get<ChildProfile>(`/children/${childId}`);
  },

  update(childId: string, input: ChildUpdateInput) {
    return apiClient.patch<ChildProfile>(`/children/${childId}`, {
      session_token: input.sessionToken,
      ...(input.name === undefined ? {} : { name: input.name }),
      ...(input.ageGroup === undefined ? {} : { age_group: input.ageGroup }),
      ...(input.age === undefined ? {} : { age: input.age }),
      ...(input.preferredLanguage === undefined
        ? {}
        : { preferred_language: input.preferredLanguage }),
    });
  },
};
