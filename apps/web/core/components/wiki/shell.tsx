import type { ReactNode } from "react";
import { useRef, useState } from "react";
import { Dialog } from "@headlessui/react";
import { WikiSidebar } from "./sidebar/root";

export function WikiShell({ children }: { children: ReactNode }) {
  const [isDrawerOpen, setDrawerOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(256);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const handleNavigate = () => {
    setDrawerOpen(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  };

  const startResize = (event: React.PointerEvent<HTMLDivElement>) => {
    const startX = event.clientX;
    const initialWidth = sidebarWidth;
    const handleMove = (moveEvent: PointerEvent) =>
      setSidebarWidth(Math.min(420, Math.max(200, initialWidth + moveEvent.clientX - startX)));
    const handleUp = () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp, { once: true });
  };

  return (
    <div className="flex size-full overflow-hidden rounded-lg border border-subtle bg-surface-1">
      <aside
        className="relative hidden h-full shrink-0 border-r border-subtle md:block"
        style={{ width: sidebarWidth }}
      >
        <WikiSidebar onNavigate={() => {}} />
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize Wiki sidebar"
          className="focus-visible:outline-accent-primary absolute top-0 -right-1 z-10 h-full w-2 cursor-col-resize focus-visible:outline-2"
          onPointerDown={startResize}
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") setSidebarWidth((width) => Math.max(200, width - 16));
            if (event.key === "ArrowRight") setSidebarWidth((width) => Math.min(420, width + 16));
          }}
        />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-subtle p-2 md:hidden">
          <button
            ref={triggerRef}
            type="button"
            aria-label="Open Wiki navigation"
            onClick={() => setDrawerOpen(true)}
            className="focus-visible:outline-accent-primary rounded px-2 py-1 text-13 font-medium focus-visible:outline-2"
          >
            ☰ Wiki
          </button>
        </div>
        <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      </div>
      <Dialog open={isDrawerOpen} onClose={setDrawerOpen} className="relative z-50 md:hidden">
        <div className="fixed inset-0 bg-black/40 motion-reduce:transition-none" aria-hidden="true" />
        <div className="fixed inset-0 flex">
          <Dialog.Panel className="shadow-lg h-full w-[min(86vw,320px)] border-r border-subtle bg-surface-1 motion-reduce:transition-none">
            <Dialog.Title className="sr-only">Wiki navigation</Dialog.Title>
            <WikiSidebar onNavigate={handleNavigate} />
          </Dialog.Panel>
        </div>
      </Dialog>
    </div>
  );
}
