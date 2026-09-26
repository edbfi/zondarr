<script lang="ts">
/**
 * Test wrapper for the join page component.
 *
 * Allows testing the join page with mock data without SvelteKit's load function.
 *
 * @module routes/(public)/join/[code]/join-page-test-wrapper
 */

import { AlertTriangle, Calendar, CheckCircle, Library, Server } from '@lucide/svelte';
import type { InvitationValidationResponse } from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';

interface Props {
	code: string;
	validation: InvitationValidationResponse | null;
	error: Error | null;
}

const { code, validation, error }: Props = $props();

/**
 * Map failure reasons to user-friendly messages.
 */
function getFailureMessage(reason: string | null | undefined): string {
	switch (reason) {
		case 'not_found':
			return 'This invitation code does not exist. Please check the code and try again.';
		case 'disabled':
			return 'This invitation has been disabled by the administrator.';
		case 'expired':
			return 'This invitation has expired and is no longer valid.';
		case 'max_uses_reached':
			return 'This invitation has reached its maximum number of uses.';
		default:
			return 'This invitation code is not valid.';
	}
}
</script>

<div class="space-y-6" data-join-page>
	<!-- Page header -->
	<div class="text-center">
		<h1 class="text-2xl font-bold text-cr-text md:text-3xl">Join Media Server</h1>
		<p class="mt-2 text-cr-text-muted">Validate your invitation code to get started</p>
	</div>

	<!-- Error state -->
	{#if error}
		<div data-error-state class="text-rose-400">Error: {error.message}</div>
	<!-- Invalid code state -->
	{:else if validation && !validation.valid}
		<Card data-invalid-code class="border-rose-500/30 bg-rose-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-rose-500/15 p-2 text-rose-400">
						<AlertTriangle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">Invalid Invitation</CardTitle>
						<CardDescription class="text-cr-text-muted">
							Code: <span class="font-mono" data-code>{code}</span>
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent>
				<p data-failure-reason={validation.failure_reason} class="text-cr-text-muted">
					{getFailureMessage(validation.failure_reason)}
				</p>
			</CardContent>
		</Card>
	<!-- Valid code state -->
	{:else if validation?.valid}
		<Card data-valid-code class="border-emerald-500/30 bg-emerald-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-emerald-500/15 p-2 text-emerald-400">
						<CheckCircle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">Valid Invitation</CardTitle>
						<CardDescription class="text-cr-text-muted">
							Code: <span class="font-mono" data-code>{code}</span>
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent class="space-y-6">
				<!-- Duration info -->
				{#if validation.duration_days}
					<div
						data-duration-display
						class="flex items-center gap-3 rounded-lg border border-cr-border bg-cr-bg p-4"
					>
						<div class="rounded-full bg-cr-accent/15 p-2 text-cr-accent">
							<Calendar class="size-5" />
						</div>
						<div>
							<p class="font-medium text-cr-text">Access Duration</p>
							<p class="text-sm text-cr-text-muted">
								Your access will be valid for
								<span class="font-semibold text-cr-accent" data-duration-value
									>{validation.duration_days}</span
								>
								days after registration.
							</p>
						</div>
					</div>
				{/if}

				<!-- Target servers -->
				{#if (validation.target_servers?.length ?? 0) > 0}
					<div data-target-servers>
						<div class="mb-3 flex items-center gap-2 text-cr-text">
							<Server class="size-4" />
							<h3 class="font-medium">Target Servers</h3>
						</div>
						<div class="space-y-2">
							{#each validation.target_servers as server}
								<div
									data-server-item={server.name}
									class="rounded-lg border border-cr-border bg-cr-bg p-3"
								>
									<p class="font-medium text-cr-text" data-server-name>{server.name}</p>
									<p class="text-sm text-cr-text-muted capitalize" data-server-type>
										{server.server_type}
									</p>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Allowed libraries -->
				{#if (validation.allowed_libraries?.length ?? 0) > 0}
					<div data-allowed-libraries>
						<div class="mb-3 flex items-center gap-2 text-cr-text">
							<Library class="size-4" />
							<h3 class="font-medium">Allowed Libraries</h3>
						</div>
						<div class="flex flex-wrap gap-2">
							{#each validation.allowed_libraries as library}
								<span
									data-library-item={library.id}
									class="rounded-full border border-cr-border bg-cr-bg px-3 py-1 text-sm text-cr-text"
								>
									{library.name}
								</span>
							{/each}
						</div>
					</div>
				{:else if (validation.target_servers?.length ?? 0) > 0}
					<div data-all-libraries class="flex items-center gap-2 text-cr-text-muted">
						<Library class="size-4" />
						<p class="text-sm">Access to all libraries on target servers</p>
					</div>
				{/if}

				<!-- Continue button -->
				<Button class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover">
					Continue to Registration
				</Button>
			</CardContent>
		</Card>
	{/if}
</div>
