<script lang="ts">
import type { Snippet } from 'svelte';
import { page } from '$app/state';
import { cn } from '$lib/utils.js';

interface Props {
	href: string;
	icon?: Snippet;
	children: Snippet;
}

const { href, icon, children }: Props = $props();

const isActive = $derived(page.url.pathname.startsWith(href));
</script>

<a
	{href}
	class={cn(
	'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
	'hover:bg-cr-surface hover:text-cr-accent',
	isActive ? 'bg-cr-surface text-cr-accent border-l-2 border-cr-accent' : 'text-cr-text-muted'
)}
	aria-current={isActive ? 'page' : undefined}
>
	{#if icon}
		<span class="size-5 shrink-0"> {@render icon()} </span>
	{/if}
	<span>{@render children()}</span>
</a>
