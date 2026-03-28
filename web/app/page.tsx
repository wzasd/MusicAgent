'use client';

import { useRouter } from 'next/navigation';
import ProductIntro from '@/components/Landing/ProductIntro';

export default function Home() {
  const router = useRouter();

  const navigateWithPrompt = (prompt: string) => {
    router.push(`/recommendations?prompt=${encodeURIComponent(prompt)}`);
  };

  return (
    <main className="min-h-[100dvh] bg-light-primary flex flex-col">
      <ProductIntro
        onPrimaryAction={() => router.push('/recommendations')}
        onSecondaryAction={() => router.push('/search')}
        onQuickExampleSelect={navigateWithPrompt}
      />
    </main>
  );
}

