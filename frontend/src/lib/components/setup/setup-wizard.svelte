<script lang="ts">
import { goto } from '$app/navigation';
import { advanceOnboarding, getErrorDetail, type OnboardingStep } from '$lib/api/auth';
import StepAdmin from './step-admin.svelte';
import StepCsrf from './step-csrf.svelte';
import StepIndicator from './step-indicator.svelte';
import StepServer from './step-server.svelte';
import StepTotp from './step-totp.svelte';

interface Props {
	initialStep?: OnboardingStep;
	tokenAvailable?: boolean;
	tokenError?: string;
}

const { initialStep = 'account', tokenAvailable, tokenError }: Props = $props();

// UI steps: 1=Account, 2=Two-Factor, 3=Security, 4=Server
// Backend onboarding states map to UI steps, skipping TOTP (frontend-only)
function onboardingStepToUiStep(step: OnboardingStep): number {
	if (step === 'account') return 1;
	if (step === 'security') return 3;
	return 4;
}

let currentStep = $state(1);
let stepInitialized = $state(false);
let advancing = $state(false);

$effect(() => {
	if (stepInitialized) return;
	currentStep = onboardingStepToUiStep(initialStep);
	stepInitialized = true;
});

const stepLabels = ['Account', 'Two-Factor', 'Security', 'Server'];

function handleAdminComplete() {
	currentStep = 2;
}

function handleTotpComplete() {
	currentStep = 3;
}

function handleTotpSkip() {
	currentStep = 3;
}

async function advanceStep(): Promise<boolean> {
	if (advancing) return false;
	advancing = true;
	try {
		const response = await advanceOnboarding();
		if (response.error) {
			console.warn('[setup wizard] failed to advance onboarding:', getErrorDetail(response.error));
			return false;
		}
		return true;
	} finally {
		advancing = false;
	}
}

async function handleServerComplete() {
	// The backend already advances onboarding from "server" → "complete" during
	// server creation (complete_server_step), so we navigate directly without
	// calling the skip endpoint again — a redundant call that could block
	// navigation on transient failure even though onboarding is already complete.
	await goto('/dashboard');
}

async function handleServerSkip() {
	const ok = await advanceStep();
	if (!ok) return;
	await goto('/dashboard');
}

function handleCsrfComplete() {
	currentStep = 4;
}

async function handleCsrfSkip() {
	const ok = await advanceStep();
	if (!ok) return;
	currentStep = 4;
}
</script>

<style>
@keyframes step-enter {
	from {
		opacity: 0;
		transform: translateY(16px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

.step-content {
	animation: step-enter 0.4s ease-out;
}
</style>

<div class="flex flex-col gap-4">
	<StepIndicator {currentStep} totalSteps={4} {stepLabels} />

	{#key currentStep}
		<div class="step-content">
			{#if currentStep === 1}
				<StepAdmin onComplete={handleAdminComplete} {tokenAvailable} {tokenError} />
			{:else if currentStep === 2}
				<StepTotp onComplete={handleTotpComplete} onSkip={handleTotpSkip} />
			{:else if currentStep === 3}
				<StepCsrf onComplete={handleCsrfComplete} onSkip={handleCsrfSkip} />
			{:else}
				<StepServer onComplete={handleServerComplete} onSkip={handleServerSkip} />
			{/if}
		</div>
	{/key}
</div>
