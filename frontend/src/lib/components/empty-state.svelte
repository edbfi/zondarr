<script lang="ts">
import { Inbox } from '@lucide/svelte';
import type { Snippet } from 'svelte';
import { Button } from '$lib/components/ui/button';
import { cn } from '$lib/utils.js';

interface Action {
	label: string;
	onClick: () => void;
}

interface Props {
	title: string;
	description?: string;
	action?: Action;
	icon?: Snippet;
	class?: string;
}

const { title, description, action, icon, class: className }: Props = $props();
</script>

<div
	data-empty-state
	class={cn(
	'flex flex-col items-center justify-center rounded-lg border border-dashed border-cr-border bg-cr-surface/50 px-6 py-12 text-center',
	className
)}
	role="status"
	aria-label={title}
>
	<!-- Icon -->
	<div class="mb-4 rounded-full bg-cr-border/50 p-3 text-cr-text-muted">
		{#if icon}
			{@render icon()}
		{:else}
			<Inbox class="size-8" />
		{/if}
	</div>

	<!-- Title -->
	<h3 class="text-lg font-semibold text-cr-text">{title}</h3>

	<!-- Description -->
	{#if description}
		<p class="mt-1 max-w-sm text-sm text-cr-text-muted">{description}</p>
	{/if}

	<!-- Action button -->
	{#if action}
		<Button onclick={action.onClick} class="mt-4 bg-cr-accent text-cr-bg hover:bg-cr-accent-hover">
			{action.label}
		</Button>
	{/if}
</div>
