// @vitest-environment jsdom

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  Show,
  Hide,
  MobileOnly,
  DesktopOnly,
  MobileSheet,
  ResponsiveContainer,
  TouchTarget,
} from './Responsive';

describe('Show', () => {
  it('renders children', () => {
    render(<Show minWidth="md">desktop content</Show>);
    expect(screen.getByText('desktop content')).toBeDefined();
  });

  it('applies correct responsive class', () => {
    const { container } = render(<Show minWidth="md">content</Show>);
    expect(container.firstChild).toHaveClass('hidden', 'md:block');
  });
});

describe('Hide', () => {
  it('renders children', () => {
    render(<Hide minWidth="md">hidden content</Hide>);
    expect(screen.getByText('hidden content')).toBeDefined();
  });

  it('applies correct responsive class', () => {
    const { container } = render(<Hide minWidth="md">content</Hide>);
    expect(container.firstChild).toHaveClass('md:hidden');
  });
});

describe('MobileOnly', () => {
  it('renders children', () => {
    render(<MobileOnly>mobile only</MobileOnly>);
    expect(screen.getByText('mobile only')).toBeDefined();
  });

  it('applies md:hidden class', () => {
    const { container } = render(<MobileOnly>content</MobileOnly>);
    expect(container.firstChild).toHaveClass('md:hidden');
  });
});

describe('DesktopOnly', () => {
  it('renders children', () => {
    render(<DesktopOnly>desktop only</DesktopOnly>);
    expect(screen.getByText('desktop only')).toBeDefined();
  });

  it('applies hidden md:block class', () => {
    const { container } = render(<DesktopOnly>content</DesktopOnly>);
    expect(container.firstChild).toHaveClass('hidden', 'md:block');
  });
});

describe('MobileSheet', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <MobileSheet open={false} onClose={() => {}}>
        content
      </MobileSheet>,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders sheet content when open', () => {
    render(
      <MobileSheet open title="Sheet Title" onClose={() => {}}>
        <p>Sheet content</p>
      </MobileSheet>,
    );
    expect(screen.getByText('Sheet Title')).toBeDefined();
    expect(screen.getByText('Sheet content')).toBeDefined();
  });

  it('renders dialog role when open', () => {
    render(
      <MobileSheet open onClose={() => {}}>
        content
      </MobileSheet>,
    );
    expect(screen.getByRole('dialog')).toBeDefined();
  });

  it('has close button', () => {
    render(
      <MobileSheet open onClose={() => {}}>
        content
      </MobileSheet>,
    );
    const closeBtn = screen.getByRole('button');
    expect(closeBtn).toBeDefined();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    render(
      <MobileSheet open onClose={onClose}>
        content
      </MobileSheet>,
    );
    fireEvent.click(screen.getByRole('button'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('renders with default snap point', () => {
    render(
      <MobileSheet open onClose={() => {}}>
        content
      </MobileSheet>,
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog.style.height).toContain('vh');
  });
});

describe('ResponsiveContainer', () => {
  it('renders children', () => {
    render(<ResponsiveContainer>container content</ResponsiveContainer>);
    expect(screen.getByText('container content')).toBeDefined();
  });

  it('applies safe area padding', () => {
    const { container } = render(<ResponsiveContainer>content</ResponsiveContainer>);
    expect(container.firstChild).toHaveClass('pb-[max(1rem,env(safe-area-inset-bottom))]');
  });

  it('respects padding prop', () => {
    const { container } = render(<ResponsiveContainer padding="lg">content</ResponsiveContainer>);
    expect(container.firstChild).toHaveClass('px-4', 'py-5');
  });
});

describe('TouchTarget', () => {
  it('renders children', () => {
    render(
      <TouchTarget ariaLabel="test button">
        <span>touch target</span>
      </TouchTarget>,
    );
    expect(screen.getByText('touch target')).toBeDefined();
  });

  it('applies touch-friendly size', () => {
    const { container } = render(<TouchTarget>target</TouchTarget>);
    expect(container.firstChild).toHaveClass('min-h-[44px]', 'min-w-[44px]');
  });

  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(
      <TouchTarget onClick={onClick} ariaLabel="button">
        click me
      </TouchTarget>,
    );
    fireEvent.click(screen.getByText('click me'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('renders as button element', () => {
    const { container } = render(<TouchTarget>button</TouchTarget>);
    expect(container.querySelector('button')).toBeDefined();
  });
});
