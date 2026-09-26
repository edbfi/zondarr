<script lang="ts">
import type { Snippet } from 'svelte';
import ThemeToggle from '$lib/components/theme-toggle.svelte';

interface Props {
	children: Snippet;
}

const { children }: Props = $props();
</script>

<div class="relative flex min-h-screen flex-col items-center justify-center bg-cr-bg px-4 py-8">
	<!-- Theme toggle -->
	<div class="absolute right-4 top-4">
		<ThemeToggle />
	</div>

	<!-- Logo -->
	<div class="mb-8 flex flex-col items-center gap-3">
		<img src="/zondarr-logo.svg" alt="Zondarr" class="h-16 w-16">
		<span class="font-display text-xl font-bold tracking-tight text-cr-accent">Zondarr</span>
	</div>

	<!-- Content slot -->
	<div class="w-full max-w-lg">
		{@render children()}
	</div>
</div>
