import type { Metadata } from "next";

import Dashboard from "@/components/Dashboard";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Counselor dashboard · Clairvoyance",
};

export default function DashboardPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.title}>Counselor dashboard</h1>
      <Dashboard />
    </main>
  );
}
