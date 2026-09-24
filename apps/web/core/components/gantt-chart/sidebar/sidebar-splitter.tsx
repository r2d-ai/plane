/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useRef } from "react";
import { GANTT_SIDEBAR_MAX_WIDTH, GANTT_SIDEBAR_MIN_WIDTH } from "@/hooks/use-gantt-preferences";

type Props = {
  onResize: (width: number) => void;
};

export function SidebarSplitter(props: Props) {
  const { onResize } = props;
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);

  const onPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      const sidebar = document.getElementById("gantt-sidebar");
      if (!sidebar) return;

      startXRef.current = e.clientX;
      startWidthRef.current = sidebar.offsetWidth;

      const handleMove = (moveEvent: PointerEvent) => {
        const delta = moveEvent.clientX - startXRef.current;
        const newWidth = Math.min(
          GANTT_SIDEBAR_MAX_WIDTH,
          Math.max(GANTT_SIDEBAR_MIN_WIDTH, startWidthRef.current + delta)
        );
        onResize(newWidth);
      };

      const handleUp = () => {
        window.removeEventListener("pointermove", handleMove);
        window.removeEventListener("pointerup", handleUp);
      };

      window.addEventListener("pointermove", handleMove);
      window.addEventListener("pointerup", handleUp);
    },
    [onResize]
  );

  return (
    <div
      data-gantt-sidebar-splitter
      className="absolute top-0 right-0 z-20 h-full w-1 cursor-col-resize hover:bg-accent-primary/30"
      onPointerDown={onPointerDown}
      role="separator"
      aria-orientation="vertical"
    />
  );
}
