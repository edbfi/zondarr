<script lang="ts">
/**
 * Join page for invitation code validation and redemption.
 *
 * Displays:
 * - Loading state during validation
 * - Pre-wizard flow (if configured) before registration
 * - Target servers and allowed libraries for valid codes
 * - Duration information if set
 * - Error messages for invalid codes with failure reasons
 * - Registration form for credential-based servers
 * - OAuth flow for OAuth-based servers
 * - Post-wizard flow (if configured) after registration
 * - Success page after successful registration
 *
 * @module routes/(public)/join/[code]/+page
 */

import {
	AlertTriangle,
	ArrowLeft,
	Calendar,
	CheckCircle,
	Library,
	Loader2,
	RefreshCw,
	Server,
	WifiOff
} from '@lucide/svelte';
import { toast } from 'svelte-sonner';
import { browser } from '$app/environment';
import { invalidateAll } from '$app/navigation';
import {
	checkJoinHealth,
	type JoinHealthResponse,
	type RedemptionErrorResponse,
	type RedemptionResponse,
	redeemInvitation,
	type WizardDetailResponse
} from '$lib/api/client';
import { getErrorMessage, isNetworkError } from '$lib/api/errors';
import ErrorState from '$lib/components/error-state.svelte';
import {
	OAuthJoinFlow,
	RegistrationError,
	RegistrationForm,
	SuccessPage
} from '$lib/components/join';
import { Button } from '$lib/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';
import { Skeleton } from '$lib/components/ui/skeleton';
import { WizardShell } from '$lib/components/wizard';
import {
	type RegistrationInput,
	registrationSchema,
	sanitizeEmailToUsername,
	transformRegistrationFormData
} from '$lib/schemas/join';
import { getProvider, getProviderLabel } from '$lib/stores/providers.svelte';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();

// Flow state - extended to include wizard steps
type FlowStep =
	| 'validation'
	| 'pre_wizard'
	| 'registration'
	| 'oauth'
	| 'oauth_redeeming'
	| 'post_wizard'
	| 'success'
	| 'error';
let currentStep = $state<FlowStep>('validation');

// Loading states
let isRetrying = $state(false);
let isSubmitting = $state(false);

// Form data
let formData = $state<RegistrationInput>({
	username: '',
	password: '',
	email: ''
});
let formErrors = $state<Record<string, string[]>>({});

// OAuth state
let oauthEmail = $state<string | null>(null);
let oauthRedemptionToken = $state<string | null>(null);

// Response data
let redemptionResponse = $state<RedemptionResponse | null>(null);
let redemptionError = $state<RedemptionErrorResponse | null>(null);

// Health gate state
let isCheckingHealth = $state(false);
let healthResult = $state<JoinHealthResponse | null>(null);
let healthError = $state<string | null>(null);

// Wizard state
let preWizardCompleted = $state(false);
let postWizardCompleted = $state(false);
let preWizardToken = $state<string | null>(null);

// Derive whether any target server is Plex (for success page)
const hasPlexServer = $derived(
	data.validation?.target_servers?.some((s) => s.server_type === 'plex') ?? false
);

// Determine join flow type from provider metadata
const hasCredentialCreateServer = $derived(
	data.validation?.target_servers?.some((s) => {
		const provider = getProvider(s.server_type);
		return provider?.join_flow_type === 'credential_create';
	}) ?? false
);

const hasOAuthLinkServer = $derived(
	data.validation?.target_servers?.some((s) => {
		const provider = getProvider(s.server_type);
		return provider?.join_flow_type === 'oauth_link';
	}) ?? false
);

// Get the first OAuth server type for branding
const oauthServerType = $derived(
	data.validation?.target_servers?.find((s) => {
		const provider = getProvider(s.server_type);
		return provider?.join_flow_type === 'oauth_link';
	})?.server_type ?? ''
);

// Check if invitation has pre-wizard
const hasPreWizard = $derived(
	data.validation?.valid === true && (data.validation?.pre_wizard?.steps?.length ?? 0) > 0
);

// Check if invitation has post-wizard
const hasPostWizard = $derived(
	data.validation?.valid === true && (data.validation?.post_wizard?.steps?.length ?? 0) > 0
);

// Session storage key for wizard progress
const getWizardStorageKey = (wizardId: string) => `wizard-${wizardId}-progress`;
const getJoinFlowStorageKey = (code: string) => `join-flow-${code}`;

// Restore join flow state from session storage on mount
$effect(() => {
	if (browser && data.code) {
		const saved = sessionStorage.getItem(getJoinFlowStorageKey(data.code));
		if (saved) {
			try {
				const parsed = JSON.parse(saved);
				preWizardCompleted = parsed.preWizardCompleted ?? false;
				postWizardCompleted = parsed.postWizardCompleted ?? false;
				preWizardToken = parsed.preWizardToken ?? null;
				// Restore redemption response if we were in post-wizard
				if (parsed.redemptionResponse) {
					redemptionResponse = parsed.redemptionResponse;
				}
			} catch {
				// Invalid saved state, start fresh
			}
		}
	}
});

// Scroll to top when flow phase changes
$effect(() => {
	// Track currentStep to trigger on phase changes
	void currentStep;
	if (browser) {
		const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		window.scrollTo({ top: 0, behavior: prefersReducedMotion ? 'instant' : 'smooth' });
	}
});

// Persist join flow state to session storage
$effect(() => {
	if (browser && data.code) {
		sessionStorage.setItem(
			getJoinFlowStorageKey(data.code),
			JSON.stringify({
				preWizardCompleted,
				postWizardCompleted,
				preWizardToken,
				redemptionResponse: redemptionResponse
			})
		);
	}
});

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

/**
 * Handle retry after error.
 */
async function handleRetry() {
	isRetrying = true;
	try {
		await invalidateAll();
	} finally {
		isRetrying = false;
	}
}

/**
 * Proceed after health gate passes — go to pre-wizard or registration.
 */
function proceedAfterHealthGate() {
	// Check if pre-wizard needs to be completed first
	if (hasPreWizard && !preWizardCompleted) {
		currentStep = 'pre_wizard';
		return;
	}

	// Determine which registration flow to use based on server types
	if (hasOAuthLinkServer && !hasCredentialCreateServer) {
		currentStep = 'oauth';
	} else {
		currentStep = 'registration';
	}
}

/**
 * Proceed to registration flow — runs health gate first.
 *
 * Checks that all target servers are reachable before allowing the user
 * to start registration or OAuth. This prevents frustrating failures
 * partway through the flow when servers are down.
 */
async function handleContinue() {
	isCheckingHealth = true;
	healthError = null;
	healthResult = null;

	try {
		const result = await checkJoinHealth(data.code);

		if (result.error) {
			if (result.status === 404) {
				// 404 means the invitation code is invalid or expired — do not proceed
				toast.error('This invitation code is no longer valid.');
				return;
			}
			// Other errors (5xx, network flaky, endpoint not deployed) — allow proceeding
			proceedAfterHealthGate();
			return;
		}

		if (!result.data) {
			proceedAfterHealthGate();
			return;
		}

		healthResult = result.data;

		const unreachable = result.data.servers.filter((s) => !s.reachable);
		if (result.data.all_reachable || unreachable.length === 0) {
			proceedAfterHealthGate();
		} else {
			// Some servers unreachable — show health gate
			toast.error(`${unreachable.length} server${unreachable.length > 1 ? 's' : ''} unreachable`);
		}
	} catch {
		// Network error on health check itself — allow proceeding
		proceedAfterHealthGate();
	} finally {
		isCheckingHealth = false;
	}
}

/**
 * Retry the health gate check.
 */
async function retryHealthCheck() {
	await handleContinue();
}

/**
 * Skip the health gate and proceed anyway (user override).
 */
function skipHealthGate() {
	healthResult = null;
	healthError = null;
	proceedAfterHealthGate();
}

/**
 * Go back to validation step.
 */
function handleBack() {
	currentStep = 'validation';
	formErrors = {};
	oauthEmail = null;
	oauthRedemptionToken = null;
}

/**
 * Handle pre-wizard completion.
 */
function handlePreWizardComplete(completionToken?: string | null) {
	preWizardCompleted = true;
	preWizardToken = completionToken ?? null;
	// Proceed to registration
	if (hasOAuthLinkServer && !hasCredentialCreateServer) {
		currentStep = 'oauth';
	} else {
		currentStep = 'registration';
	}
}

/**
 * Handle pre-wizard cancellation/abandonment.
 * No accounts created if pre-wizard abandoned
 */
function handlePreWizardCancel() {
	// Clear wizard progress from session storage
	if (browser && data.validation?.pre_wizard?.id) {
		sessionStorage.removeItem(getWizardStorageKey(data.validation.pre_wizard.id));
	}
	// Clear join flow state
	if (browser && data.code) {
		sessionStorage.removeItem(getJoinFlowStorageKey(data.code));
	}
	// Reset state
	preWizardCompleted = false;
	preWizardToken = null;
	currentStep = 'validation';
}

/**
 * Handle post-wizard completion.
 */
function handlePostWizardComplete() {
	postWizardCompleted = true;
	// Clear join flow state on successful completion
	if (browser && data.code) {
		sessionStorage.removeItem(getJoinFlowStorageKey(data.code));
	}
	currentStep = 'success';
}

/**
 * Handle post-wizard cancellation.
 * Note: Account is already created at this point, so we just skip to success.
 */
function handlePostWizardCancel() {
	// Clear wizard progress from session storage
	if (browser && data.validation?.post_wizard?.id) {
		sessionStorage.removeItem(getWizardStorageKey(data.validation.post_wizard.id));
	}
	postWizardCompleted = true;
	currentStep = 'success';
}

/**
 * Handle registration form submission.
 */
async function handleRegistrationSubmit() {
	// Validate form data
	const result = registrationSchema.safeParse(formData);
	if (!result.success) {
		// Transform Zod errors to our format
		const errors: Record<string, string[]> = {};
		for (const issue of result.error.issues) {
			const field = issue.path[0] as string;
			if (!errors[field]) {
				errors[field] = [];
			}
			errors[field].push(issue.message);
		}
		formErrors = errors;
		return;
	}

	// Clear errors and submit
	formErrors = {};
	isSubmitting = true;

	try {
		const apiData = {
			...transformRegistrationFormData(result.data),
			pre_wizard_token: preWizardToken ?? undefined
		};
		const response = await redeemInvitation(data.code, apiData);

		if (response.error) {
			// Handle API error response - cast through unknown for type safety
			const errorBody = response.error as unknown as RedemptionErrorResponse;
			if (errorBody.error_code) {
				redemptionError = errorBody;
				currentStep = 'error';
				toast.error(errorBody.message || 'Registration failed');
			} else {
				toast.error('An unexpected error occurred');
			}
			return;
		}

		if (response.data) {
			// Check if it's an error response (has error_code)
			const responseData = response.data as RedemptionResponse | RedemptionErrorResponse;
			if ('error_code' in responseData) {
				redemptionError = responseData as RedemptionErrorResponse;
				currentStep = 'error';
				toast.error(redemptionError.message || 'Registration failed');
			} else if (responseData.success) {
				redemptionResponse = responseData as RedemptionResponse;
				// Check if post-wizard needs to be shown
				if (hasPostWizard && !postWizardCompleted) {
					currentStep = 'post_wizard';
					toast.success('Account created! Please complete the final steps.');
				} else {
					currentStep = 'success';
					toast.success('Account created successfully!');
				}
			} else {
				toast.error('Registration failed');
			}
		}
	} catch (err) {
		toast.error(getErrorMessage(err));
	} finally {
		isSubmitting = false;
	}
}

/**
 * Handle OAuth authentication success.
 */
async function handleOAuthAuthenticated(email: string, redemptionToken: string) {
	oauthEmail = email;
	oauthRedemptionToken = redemptionToken;
	currentStep = 'oauth_redeeming';

	// Proceed to redeem the invitation with the one-time redemption token
	// Use the email as username and a placeholder password
	// The backend resolves the redemption token to the real auth_token server-side
	try {
		const response = await redeemInvitation(data.code, {
			username: sanitizeEmailToUsername(email),
			password: 'oauth_placeholder', // Placeholder - backend handles OAuth auth differently
			email: email,
			redemption_token: redemptionToken,
			pre_wizard_token: preWizardToken ?? undefined
		});

		if (response.error) {
			// Cast through unknown for type safety
			const errorBody = response.error as unknown as RedemptionErrorResponse;
			if (errorBody.error_code) {
				redemptionError = errorBody;
				currentStep = 'error';
				toast.error(errorBody.message || 'Registration failed');
			} else {
				toast.error('An unexpected error occurred');
			}
			return;
		}

		if (response.data) {
			const responseData = response.data as RedemptionResponse | RedemptionErrorResponse;
			if ('error_code' in responseData) {
				redemptionError = responseData as RedemptionErrorResponse;
				currentStep = 'error';
				toast.error(redemptionError.message || 'Registration failed');
			} else if (responseData.success) {
				redemptionResponse = responseData as RedemptionResponse;
				// Check if post-wizard needs to be shown
				if (hasPostWizard && !postWizardCompleted) {
					currentStep = 'post_wizard';
					toast.success('Added to server! Please complete the final steps.');
				} else {
					currentStep = 'success';
					toast.success('Successfully added to server!');
				}
			} else {
				toast.error('Registration failed');
			}
		}
	} catch (err) {
		redemptionError = {
			success: false,
			error_code: 'NETWORK_ERROR',
			message: getErrorMessage(err)
		};
		currentStep = 'error';
		toast.error(getErrorMessage(err));
	}
}

/**
 * Handle OAuth cancellation.
 */
function handleOAuthCancel() {
	currentStep = 'validation';
	oauthEmail = null;
	oauthRedemptionToken = null;
}

/**
 * Handle retry after registration error.
 */
function handleRegistrationRetry() {
	redemptionError = null;
	oauthEmail = null;
	oauthRedemptionToken = null;
	// Go back to appropriate registration step
	if (hasOAuthLinkServer && !hasCredentialCreateServer) {
		currentStep = 'oauth';
	} else {
		currentStep = 'registration';
	}
}
</script>

<svelte:head>
	<!-- Prevent invitation code in URL from leaking via Referer header to OAuth providers -->
	<meta name="referrer" content="no-referrer">
</svelte:head>

<div class="space-y-4">
	<!-- Page header -->
	<div class="text-center">
		<h1 class="text-2xl font-bold text-cr-text md:text-3xl">Join Media Server</h1>
		<p class="mt-2 text-cr-text-muted">
			{#if currentStep === 'validation'}
				Validate your invitation code to get started
			{:else if currentStep === 'pre_wizard' || currentStep === 'post_wizard'}
				Complete the required steps to continue
			{:else if currentStep === 'registration'}
				Create your account
			{:else if currentStep === 'oauth'}
				Sign in to continue
			{:else if currentStep === 'oauth_redeeming'}
				Adding you to the server...
			{:else if currentStep === 'success'}
				Welcome aboard!
			{:else}
				Something went wrong
			{/if}
		</p>
	</div>

	<!-- Loading state -->
	{#if isRetrying}
		<div class="mx-auto w-full max-w-lg">
			<Card class="border-cr-border bg-cr-surface">
				<CardHeader>
					<Skeleton class="h-6 w-48" />
					<Skeleton class="mt-2 h-4 w-64" />
				</CardHeader>
				<CardContent class="space-y-4">
					<Skeleton class="h-20 w-full" />
					<Skeleton class="h-20 w-full" />
				</CardContent>
			</Card>
		</div>
	<!-- Error state (network/validation error) -->
	{:else if data.error}
		<div class="mx-auto w-full max-w-lg">
			<ErrorState
				message={getErrorMessage(data.error)}
				title={isNetworkError(data.error) ? 'Connection Error' : 'Validation Failed'}
				onRetry={handleRetry}
			/>
		</div>
	<!-- Invalid code state -->
	{:else if data.validation && !data.validation.valid}
		<div class="mx-auto w-full max-w-lg">
			<Card class="border-rose-500/30 bg-rose-500/5">
				<CardHeader>
					<div class="flex items-center gap-3">
						<div class="rounded-full bg-rose-500/15 p-2 text-rose-400">
							<AlertTriangle class="size-5" />
						</div>
						<div>
							<CardTitle class="text-cr-text">Invalid Invitation</CardTitle>
							<CardDescription class="text-cr-text-muted">
								Code: <span class="font-mono">{data.code}</span>
							</CardDescription>
						</div>
					</div>
				</CardHeader>
				<CardContent>
					<p data-failure-reason={data.validation.failure_reason} class="text-cr-text-muted">
						{getFailureMessage(data.validation.failure_reason)}
					</p>
				</CardContent>
			</Card>
		</div>
	<!-- Pre-wizard state -->
	{:else if currentStep === 'pre_wizard' && data.validation?.pre_wizard}
		<WizardShell
			wizard={data.validation.pre_wizard}
			onComplete={handlePreWizardComplete}
			onCancel={handlePreWizardCancel}
			storageScope={data.code}
		/>
	<!-- Post-wizard state -->
	{:else if currentStep === 'post_wizard' && data.validation?.post_wizard}
		<WizardShell
			wizard={data.validation.post_wizard}
			onComplete={handlePostWizardComplete}
			onCancel={handlePostWizardCancel}
			storageScope={data.code}
		/>
	<!-- Success state -->
	{:else if currentStep === 'success' && redemptionResponse}
		<div class="mx-auto w-full max-w-lg">
			<SuccessPage response={redemptionResponse} {hasPlexServer} />
		</div>
	<!-- Registration error state -->
	{:else if currentStep === 'error' && redemptionError}
		<div class="mx-auto w-full max-w-lg">
			<RegistrationError error={redemptionError} onRetry={handleRegistrationRetry} />
		</div>
	<!-- Registration form state -->
	{:else if currentStep === 'registration' && data.validation?.valid}
		<div class="mx-auto w-full max-w-lg">
			<Card class="border-cr-border bg-cr-surface">
				<CardHeader>
					<div class="flex items-center gap-3">
						<Button
							variant="ghost"
							size="icon"
							onclick={handleBack}
							class="text-cr-text-muted hover:text-cr-text"
							aria-label="Go back"
						>
							<ArrowLeft class="size-5" />
						</Button>
						<div>
							<CardTitle class="text-cr-text">Create Your Account</CardTitle>
							<CardDescription class="text-cr-text-muted">
								Enter your details to create your account
							</CardDescription>
						</div>
					</div>
				</CardHeader>
				<CardContent>
					{#if hasCredentialCreateServer}
						<RegistrationForm
							bind:formData
							errors={formErrors}
							submitting={isSubmitting}
							onSubmit={handleRegistrationSubmit}
						/>
					{:else}
						<p class="text-cr-text-muted">No supported server types found.</p>
					{/if}
				</CardContent>
			</Card>
		</div>
	<!-- OAuth flow state -->
	{:else if currentStep === 'oauth' && data.validation?.valid}
		<div class="mx-auto w-full max-w-lg">
			<Card class="border-cr-border bg-cr-surface">
				<CardHeader>
					<div class="flex items-center gap-3">
						<Button
							variant="ghost"
							size="icon"
							onclick={handleBack}
							class="text-cr-text-muted hover:text-cr-text"
							aria-label="Go back"
						>
							<ArrowLeft class="size-5" />
						</Button>
						<div>
							<CardTitle class="text-cr-text"
								>Sign in with {getProviderLabel(oauthServerType)}</CardTitle
							>
							<CardDescription class="text-cr-text-muted">
								Authenticate with your {getProviderLabel(oauthServerType)} account to get access
							</CardDescription>
						</div>
					</div>
				</CardHeader>
				<CardContent>
					<OAuthJoinFlow
						serverType={oauthServerType}
						onAuthenticated={handleOAuthAuthenticated}
						onCancel={handleOAuthCancel}
					/>
				</CardContent>
			</Card>
		</div>
	<!-- OAuth redeeming state -->
	{:else if currentStep === 'oauth_redeeming'}
		<div class="mx-auto w-full max-w-lg">
			<Card class="border-cr-border bg-cr-surface">
				<CardHeader>
					<CardTitle class="text-cr-text">Adding You to the Server</CardTitle>
					<CardDescription class="text-cr-text-muted">
						Please wait while we set up your access...
					</CardDescription>
				</CardHeader>
				<CardContent class="flex flex-col items-center gap-4 py-8">
					<div
						class="size-8 animate-spin rounded-full border-2 border-cr-accent border-t-transparent"
					></div>
					{#if oauthEmail}
						<p class="text-sm text-cr-text-muted">
							Signed in as <span class="font-medium text-cr-text">{oauthEmail}</span>
						</p>
					{/if}
				</CardContent>
			</Card>
		</div>
	<!-- Valid code state (validation step) -->
	{:else if data.validation?.valid}
		<div class="mx-auto w-full max-w-lg">
			<Card class="border-emerald-500/30 bg-emerald-500/5">
				<CardHeader>
					<div class="flex items-center gap-3">
						<div class="rounded-full bg-emerald-500/15 p-2 text-emerald-400">
							<CheckCircle class="size-5" />
						</div>
						<div>
							<CardTitle class="text-cr-text">Valid Invitation</CardTitle>
							<CardDescription class="text-cr-text-muted">
								Code: <span class="font-mono">{data.code}</span>
							</CardDescription>
						</div>
					</div>
				</CardHeader>
				<CardContent class="space-y-6">
					<!-- Duration info -->
					{#if data.validation.duration_days}
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
									<span class="font-semibold text-cr-accent"
										>{data.validation.duration_days}
										days</span
									>
									after registration.
								</p>
							</div>
						</div>
					{/if}

					<!-- Target servers -->
					{#if (data.validation.target_servers?.length ?? 0) > 0}
						<div data-target-servers>
							<div class="mb-3 flex items-center gap-2 text-cr-text">
								<Server class="size-4" />
								<h3 class="font-medium">Target Servers</h3>
							</div>
							<div class="space-y-2">
								{#each data.validation.target_servers as server}
									<div class="rounded-lg border border-cr-border bg-cr-bg p-3">
										<p class="font-medium text-cr-text">{server.name}</p>
										<p class="text-sm text-cr-text-muted capitalize">{server.server_type}</p>
									</div>
								{/each}
							</div>
						</div>
					{/if}

					<!-- Allowed libraries -->
					{#if (data.validation.allowed_libraries?.length ?? 0) > 0}
						<div data-allowed-libraries>
							<div class="mb-3 flex items-center gap-2 text-cr-text">
								<Library class="size-4" />
								<h3 class="font-medium">Allowed Libraries</h3>
							</div>
							<div class="flex flex-wrap gap-2">
								{#each data.validation.allowed_libraries as library}
									<span
										class="rounded-full border border-cr-border bg-cr-bg px-3 py-1 text-sm text-cr-text"
									>
										{library.name}
									</span>
								{/each}
							</div>
						</div>
					{:else if (data.validation.target_servers?.length ?? 0) > 0}
						<div class="flex items-center gap-2 text-cr-text-muted">
							<Library class="size-4" />
							<p class="text-sm">Access to all libraries on target servers</p>
						</div>
					{/if}

					<!-- Pre-wizard notice -->
					{#if hasPreWizard}
						<div
							class="flex items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4"
						>
							<div class="rounded-full bg-amber-500/15 p-2 text-amber-400">
								<AlertTriangle class="size-5" />
							</div>
							<div>
								<p class="font-medium text-cr-text">Additional Steps Required</p>
								<p class="text-sm text-cr-text-muted">
									You'll need to complete a few steps before creating your account.
								</p>
							</div>
						</div>
					{/if}

					<!-- Health gate: unreachable servers warning -->
					{#if healthResult && !healthResult.all_reachable}
						<div class="rounded-lg border border-rose-500/30 bg-rose-500/5 p-4 space-y-3">
							<div class="flex items-center gap-3">
								<div class="rounded-full bg-rose-500/15 p-2 text-rose-400">
									<WifiOff class="size-5" />
								</div>
								<div>
									<p class="font-medium text-cr-text">Server Connection Issue</p>
									<p class="text-sm text-cr-text-muted">
										Some servers are currently unreachable. Registration may fail.
									</p>
								</div>
							</div>
							<div class="space-y-1">
								{#each healthResult.servers as server}
									<div class="flex items-center gap-2 text-sm">
										{#if server.reachable}
											<CheckCircle class="size-3.5 text-emerald-400" />
											<span class="text-cr-text">{server.name}</span>
										{:else}
											<WifiOff class="size-3.5 text-rose-400" />
											<span class="text-cr-text-muted">{server.name} — unreachable</span>
										{/if}
									</div>
								{/each}
							</div>
							<div class="flex gap-2">
								<Button
									onclick={retryHealthCheck}
									disabled={isCheckingHealth}
									class="flex-1 bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
								>
									{#if isCheckingHealth}
										<Loader2 class="size-4 mr-2 animate-spin" />
										Checking...
									{:else}
										<RefreshCw class="size-4 mr-2" />
										Retry
									{/if}
								</Button>
								<Button
									variant="outline"
									onclick={skipHealthGate}
									class="border-cr-border text-cr-text-muted hover:text-cr-text"
								>
									Continue Anyway
								</Button>
							</div>
						</div>
					{:else}
						<!-- Continue button -->
						<Button
							onclick={handleContinue}
							disabled={isCheckingHealth}
							class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
						>
							{#if isCheckingHealth}
								<Loader2 class="size-4 mr-2 animate-spin" />
								Checking servers...
							{:else}
								{hasPreWizard && !preWizardCompleted ? 'Continue to Required Steps' : 'Continue to Registration'}
							{/if}
						</Button>
					{/if}
				</CardContent>
			</Card>
		</div>
	{/if}
</div>
