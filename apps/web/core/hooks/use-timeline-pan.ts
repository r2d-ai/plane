/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RefObject } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

const PAN_THRESHOLD_PX = 4;

const isEditableTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable ||
    !!target.closest("[contenteditable='true']")
  );
};

const isPanBlockedTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false;
  return !!(
    target.closest("[data-gantt-resize-handle]") ||
    target.closest("[data-gantt-sidebar-splitter]") ||
    target.closest("[data-gantt-block-move]")
  );
};

type UseTimelinePanOptions = {
  containerRef: RefObject<HTMLDivElement | null>;
  enabled?: boolean;
};

type UseTimelinePanReturn = {
  isPanning: boolean;
  isSpacePressed: boolean;
  containerProps: {
    tabIndex: number;
    onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => void;
    onPointerMove: (e: React.PointerEvent<HTMLDivElement>) => void;
    onPointerUp: (e: React.PointerEvent<HTMLDivElement>) => void;
    onPointerCancel: (e: React.PointerEvent<HTMLDivElement>) => void;
    onLostPointerCapture: (e: React.PointerEvent<HTMLDivElement>) => void;
    style: React.CSSProperties | undefined;
    "data-timeline-pan-active": string | undefined;
  };
};

export function useTimelinePan(options: UseTimelinePanOptions): UseTimelinePanReturn {
  const { containerRef, enabled = true } = options;

  const [isPanning, setIsPanning] = useState(false);
  const [isSpacePressed, setIsSpacePressed] = useState(false);

  const panStateRef = useRef<{
    pointerId: number;
    startPointerX: number;
    startPointerY: number;
    startScrollLeft: number;
    startScrollTop: number;
    isActive: boolean;
    forcePan: boolean;
  } | null>(null);

  const resetPan = useCallback(() => {
    panStateRef.current = null;
    setIsPanning(false);
  }, []);

  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat || isEditableTarget(e.target)) return;
      const container = containerRef.current;
      if (!container?.contains(document.activeElement) && document.activeElement !== container) return;
      e.preventDefault();
      setIsSpacePressed(true);
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      setIsSpacePressed(false);
      if (panStateRef.current?.forcePan) {
        const container = containerRef.current;
        if (container && panStateRef.current) {
          try {
            container.releasePointerCapture(panStateRef.current.pointerId);
          } catch {
            // pointer may already be released
          }
        }
        resetPan();
      }
    };

    const handleBlur = () => {
      setIsSpacePressed(false);
      resetPan();
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", handleBlur);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", handleBlur);
    };
  }, [containerRef, enabled, resetPan]);

  const onPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!enabled || e.button !== 0) return;
      if (isEditableTarget(e.target)) return;

      const container = containerRef.current;
      if (!container) return;

      const forcePan = isSpacePressed;
      const blocked = isPanBlockedTarget(e.target);

      if (!forcePan && blocked) return;

      // Empty chart area or force pan via Space
      if (!forcePan) {
        const isOnTask =
          e.target instanceof HTMLElement &&
          !!(e.target.closest("[data-gantt-block-move]") || e.target.closest("#gantt-sidebar"));
        if (isOnTask) return;
      }

      panStateRef.current = {
        pointerId: e.pointerId,
        startPointerX: e.clientX,
        startPointerY: e.clientY,
        startScrollLeft: container.scrollLeft,
        startScrollTop: container.scrollTop,
        isActive: false,
        forcePan,
      };

      // NOTE: intentionally NOT capturing the pointer here. Capturing on pointerdown retargets the
      // subsequent pointerup (and therefore `click`) to the container, which swallows clicks on
      // controls in the chart area such as the "scroll to work item" arrow and the add-block button.
      // The pointer is captured in `onPointerMove` instead, once the gesture has crossed the pan
      // threshold and is therefore a drag rather than a click.
    },
    [containerRef, enabled, isSpacePressed]
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const state = panStateRef.current;
      const container = containerRef.current;
      if (!state || !container || e.pointerId !== state.pointerId) return;

      const deltaX = e.clientX - state.startPointerX;
      const deltaY = e.clientY - state.startPointerY;

      if (!state.isActive) {
        if (Math.abs(deltaX) < PAN_THRESHOLD_PX && Math.abs(deltaY) < PAN_THRESHOLD_PX) return;
        state.isActive = true;
        setIsPanning(true);
        e.preventDefault();

        // Capture only now that this is a real drag, so plain clicks keep reaching the controls
        // underneath (see the note in `onPointerDown`).
        try {
          container.setPointerCapture(e.pointerId);
        } catch {
          // pointer may already be gone
        }
      }

      container.scrollLeft = state.startScrollLeft - deltaX;
      container.scrollTop = state.startScrollTop - deltaY;
    },
    [containerRef]
  );

  const onPointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const state = panStateRef.current;
      const container = containerRef.current;
      if (!state || !container || e.pointerId !== state.pointerId) return;

      try {
        container.releasePointerCapture(e.pointerId);
      } catch {
        // pointer may already be released
      }
      resetPan();
    },
    [containerRef, resetPan]
  );

  const onPointerCancel = onPointerUp;
  const onLostPointerCapture = useCallback(() => {
    resetPan();
  }, [resetPan]);

  // Only advertise a grab cursor where the gesture is actually available:
  // - `grabbing` while a pan is in progress
  // - `grab` everywhere while Space is held (force-pan works over any target)
  // Otherwise fall through to the natural cursor; the pannable chart surface opts into `grab`
  // itself (see GanttChartRowList). Previously this always returned `grab`, so the sidebar columns
  // and work item bars showed a hand cursor even though dragging them does not pan.
  const cursorStyle: React.CSSProperties | undefined = isPanning
    ? { cursor: "grabbing" }
    : isSpacePressed
      ? { cursor: "grab" }
      : undefined;

  return {
    isPanning,
    isSpacePressed,
    containerProps: {
      tabIndex: 0,
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel,
      onLostPointerCapture,
      style: cursorStyle,
      "data-timeline-pan-active": isPanning ? "true" : undefined,
    },
  };
}
