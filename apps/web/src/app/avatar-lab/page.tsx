import type { Metadata } from "next";

import AvatarLab from "@/components/avatar/AvatarLab";

export const metadata: Metadata = {
  title: "Avatar lab · Clairvoyance",
};

export default function AvatarLabPage() {
  return <AvatarLab />;
}
