<script lang="ts">
/**
 * Public route group layout.
 *
 * Provides a minimal layout for public-facing pages like the join flow.
 * Includes dark mode support via ModeWatcher from the root layout.
 *
 * @module routes/(public)/+layout
 */

import type { Snippet } from 'svelte';
import ThemeToggle from '$lib/components/theme-toggle.svelte';

interface Props {
	children: Snippet;
}

const { children }: Props = $props();
</script>

<div class="flex min-h-screen flex-col bg-cr-bg">
	<!-- Minimal header with branding and theme toggle -->
	<header
		class="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-cr-border bg-cr-bg px-4 md:px-6"
	>
		<a href="/" class="flex items-center gap-2.5 font-display text-lg font-bold text-cr-accent">
			<img src="/zondarr-logo.svg" alt="" class="size-7" aria-hidden="true">
			Zondarr
		</a>
		<ThemeToggle />
	</header>

	<!-- Main content area -->
	<main class="flex flex-1 flex-col items-center px-4 py-8 md:py-12">
		<div class="w-full max-w-3xl">
			{@render children()}
		</div>
	</main>
</div>
