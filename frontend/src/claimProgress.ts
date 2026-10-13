export const CLAIM_PROGRESS_STAGES = [
  'Submitted',
  'Sent to Service Center',
  'AI Assessment',
  'Technician Verification',
  'Repair Estimate',
  'Claim Package',
  'Insurer Review'
] as const;

const progressByStatus: Record<string, { completedThrough: number; activeStage: number | null }> = {
  draft: { completedThrough: 0, activeStage: 1 },
  submitted: { completedThrough: 2, activeStage: 3 },
  assessment_in_progress: { completedThrough: 2, activeStage: 3 },
  assessment_completed: { completedThrough: 3, activeStage: 4 },
  human_review: { completedThrough: 4, activeStage: 5 },
  under_review: { completedThrough: 5, activeStage: 6 },
  package_generated: { completedThrough: 6, activeStage: 7 },
  ready_for_insurer: { completedThrough: 6, activeStage: 7 },
  approved: { completedThrough: 7, activeStage: null },
  rejected: { completedThrough: 7, activeStage: null }
};

export const getClaimProgress = (status?: string) => {
  const normalizedStatus = (status || 'submitted').toLowerCase();
  const progress = progressByStatus[normalizedStatus] || { completedThrough: 0, activeStage: null };

  return {
    ...progress,
    normalizedStatus,
    stageStatus: (stageIndex: number): 'completed' | 'active' | 'pending' => {
      const stageNumber = stageIndex + 1;
      if (stageNumber <= progress.completedThrough) return 'completed';
      if (stageNumber === progress.activeStage) return 'active';
      return 'pending';
    }
  };
};

export const formatClaimStatus = (status?: string) =>
  (status || 'submitted')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
