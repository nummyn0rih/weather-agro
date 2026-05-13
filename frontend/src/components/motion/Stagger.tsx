import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { type ComponentPropsWithoutRef, type ReactNode } from 'react';

const containerVariants: Variants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.06,
      delayChildren: 0.04,
    },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] },
  },
};

type DivProps = ComponentPropsWithoutRef<'div'>;

interface StaggerGroupProps extends DivProps {
  children: ReactNode;
}

export function StaggerGroup({ children, ...rest }: StaggerGroupProps) {
  const prefersReducedMotion = useReducedMotion();
  if (prefersReducedMotion) {
    return <div {...rest}>{children}</div>;
  }
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      {...(rest as Record<string, unknown>)}
    >
      {children}
    </motion.div>
  );
}

interface StaggerItemProps extends DivProps {
  children: ReactNode;
}

export function StaggerItem({ children, ...rest }: StaggerItemProps) {
  const prefersReducedMotion = useReducedMotion();
  if (prefersReducedMotion) {
    return <div {...rest}>{children}</div>;
  }
  return (
    <motion.div variants={itemVariants} {...(rest as Record<string, unknown>)}>
      {children}
    </motion.div>
  );
}
