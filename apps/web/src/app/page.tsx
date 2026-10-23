import Chat from "@/components/Chat";
import styles from "./page.module.css";

export default function Home() {
  return (
    <main className={styles.main}>
      <h1 className={styles.title}>Clairvoyance</h1>
      <Chat />
    </main>
  );
}
