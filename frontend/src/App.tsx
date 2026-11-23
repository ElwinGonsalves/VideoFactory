import {AnimatePresence, motion} from 'framer-motion';
import {lazy, Suspense, useEffect} from 'react';
import {ActivityDrawer} from './components/Activity';
import {EnginesModal} from './components/Engines';
import {OnboardingModal} from './components/Onboarding';
import {NAV, Shell} from './components/Shell';
import {Toasts} from './components/Toasts';
import {Skeleton} from './components/ui';
import {useReducedMotion, useRoute} from './lib/hooks';
import {StudioProvider} from './lib/studio';

const PAGES = {
  create: lazy(() => import('./pages/Create')),
  ideas: lazy(() => import('./pages/Ideas')),
  batch: lazy(() => import('./pages/Batch')),
  library: lazy(() => import('./pages/Library')),
  schedule: lazy(() => import('./pages/Schedule')),
  settings: lazy(() => import('./pages/Settings')),
};

function Routed() {
  const route = useRoute();
  const reduce = useReducedMotion();
  const page = route.page as keyof typeof PAGES;
  const Page = PAGES[page];
  const title = NAV.find((n) => n.page === page)?.label ?? 'Create';
  useEffect(() => {
    document.title = `${title} · video-factory`;
  }, [title]);
  return (
    <Shell title={title}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={page} initial={reduce ? false : {opacity: 0, y: 6}} animate={{opacity: 1, y: 0}} exit={reduce ? undefined : {opacity: 0}} transition={{duration: 0.16, ease: [0.16, 1, 0.3, 1]}}>
          <Suspense fallback={<Skeleton className="h-96" />}>
            <Page />
          </Suspense>
        </motion.div>
      </AnimatePresence>
    </Shell>
  );
}

export default function App() {
  return (
    <StudioProvider>
      <Routed />
      <ActivityDrawer />
      <EnginesModal />
      <OnboardingModal />
      <Toasts />
    </StudioProvider>
  );
}
