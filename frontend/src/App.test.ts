import { describe, expect, it } from "vitest";

import { citationLocator } from "./App";

const citation = {
  source_id: "fixture", title: "合成资料", evidence_type: "patient_education",
  section_path: [], review_status: "approved",
};

describe("citationLocator", () => {
  it("formats a page range", () => {
    expect(citationLocator({ ...citation, page_start: 3, page_end: 5 })).toBe("第 3–5 页");
  });

  it("formats a verified video timestamp", () => {
    expect(citationLocator({ ...citation, timestamp_start_seconds: 72 })).toBe("视频 72 秒处");
  });

  it("formats a webpage section path", () => {
    expect(citationLocator({ ...citation, section_path: ["随访", "复诊准备"] })).toBe("随访 / 复诊准备");
  });

  it("does not invent a locator", () => {
    expect(citationLocator(citation)).toBe("定位信息不可用");
  });
});
