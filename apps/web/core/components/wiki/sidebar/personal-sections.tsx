import Link from "next/link";
import { useLocation } from "react-router";
import { useTranslation } from "@plane/i18n";
import type { TWikiPersonalSection } from "@plane/types";
import { getWikiPersonalPath } from "../../../helpers/wiki-routes";

const sections: { key: TWikiPersonalSection; labelKey: string }[] = [
  { key: "favorites", labelKey: "wiki.sidebar.favorites" },
  { key: "owned", labelKey: "wiki.sidebar.my_pages" },
  { key: "shared", labelKey: "wiki.sidebar.shared_with_me" },
];

export function WikiPersonalSections({ onNavigate }: { onNavigate: () => void }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  return (
    <div className="space-y-0.5 border-t border-subtle pt-2">
      {sections.map(({ key, labelKey }) => {
        const href = getWikiPersonalPath(key);
        return (
          <Link
            key={key}
            href={href}
            onClick={onNavigate}
            aria-current={pathname.replace(/\/$/, "") === href ? "page" : undefined}
            className="focus-visible:outline-accent-primary block rounded px-2 py-1.5 text-13 font-medium text-secondary hover:bg-layer-1 focus-visible:outline-2 aria-[current=page]:bg-layer-1 aria-[current=page]:text-primary"
          >
            {t(labelKey)}
          </Link>
        );
      })}
    </div>
  );
}
