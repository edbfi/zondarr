<script lang="ts">
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from '@lucide/svelte';
import { Button } from '$lib/components/ui/button';
import { cn } from '$lib/utils.js';

interface Props {
	page: number;
	pageSize: number;
	total: number;
	hasNext: boolean;
	onPageChange: (page: number) => void;
	class?: string;
}

const { page, pageSize, total, hasNext, onPageChange, class: className }: Props = $props();

// Calculate total pages
const totalPages = $derived(Math.max(1, Math.ceil(total / pageSize)));

// Calculate the range of items being displayed
const startItem = $derived(total === 0 ? 0 : (page - 1) * pageSize + 1);
const endItem = $derived(Math.min(page * pageSize, total));

// Navigation helpers
const hasPrevious = $derived(page > 1);
const canGoFirst = $derived(page > 1);
const canGoLast = $derived(page < totalPages);

function goToPage(newPage: number) {
	if (newPage >= 1 && newPage <= totalPages && newPage !== page) {
		onPageChange(newPage);
	}
}

function goFirst() {
	goToPage(1);
}

function goPrevious() {
	goToPage(page - 1);
}

function goNext() {
	goToPage(page + 1);
}

function goLast() {
	goToPage(totalPages);
}
</script>

<nav
	class={cn('flex items-center justify-between gap-4', className)}
	aria-label="Pagination navigation"
>
	<!-- Item count display -->
	<p class="text-sm text-cr-text-muted font-data">
		{#if total === 0}
			No items
		{:else}
			Showing <span class="font-medium text-cr-text">{startItem}</span>
			to <span class="font-medium text-cr-text">{endItem}</span>
			{'of'} <span class="font-medium text-cr-text">{total}</span> items
		{/if}
	</p>

	<!-- Navigation buttons -->
	<div class="flex items-center gap-1">
		<Button
			variant="outline"
			size="icon-sm"
			onclick={goFirst}
			disabled={!canGoFirst}
			aria-label="Go to first page"
			class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text-muted hover:text-cr-text disabled:opacity-40"
		>
			<ChevronsLeft class="size-4" />
		</Button>

		<Button
			variant="outline"
			size="icon-sm"
			onclick={goPrevious}
			disabled={!hasPrevious}
			aria-label="Go to previous page"
			class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text-muted hover:text-cr-text disabled:opacity-40"
		>
			<ChevronLeft class="size-4" />
		</Button>

		<!-- Page indicator -->
		<span class="px-3 text-sm font-data text-cr-text-muted">
			Page <span class="font-medium text-cr-text">{page}</span>
			{'of'} <span class="font-medium text-cr-text">{totalPages}</span>
		</span>

		<Button
			variant="outline"
			size="icon-sm"
			onclick={goNext}
			disabled={!hasNext}
			aria-label="Go to next page"
			class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text-muted hover:text-cr-text disabled:opacity-40"
		>
			<ChevronRight class="size-4" />
		</Button>

		<Button
			variant="outline"
			size="icon-sm"
			onclick={goLast}
			disabled={!canGoLast}
			aria-label="Go to last page"
			class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text-muted hover:text-cr-text disabled:opacity-40"
		>
			<ChevronsRight class="size-4" />
		</Button>
	</div>
</nav>
