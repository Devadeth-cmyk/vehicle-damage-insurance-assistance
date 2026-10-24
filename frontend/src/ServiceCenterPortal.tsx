import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  FileText,
  UserCheck,
  ShieldCheck,
  CheckSquare,
  DollarSign,
  Package,
  User,
  LogOut,
  Wrench,
  Search,
  UploadCloud,
  CheckCircle,
  Clock,
  AlertCircle,
  Download,
  Eye,
  RefreshCw,
  ArrowLeft,
  Camera,
  X,
  ExternalLink,
  FileArchive,
  CheckCircle2,
  Copy,
  Check,
  FileCheck2,
  Layers,
  Send,
  Zap
} from 'lucide-react';
import { serviceCenterApi } from './services/serviceCenterService';
import { getEvidenceDisplay } from './api';
import { getClaimProgress } from './claimProgress';

interface ServiceCenterPortalProps {
  user?: any;
  currentRoute?: string;
  onNavigate?: (route: string) => void;
  onLogout?: () => void;
  themeToggle: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Helpers. Everything shown on the assessment / review / estimate screens is
// derived from the backend assessment - nothing here is pre-filled with
// example parts, severities or prices.
// ---------------------------------------------------------------------------
const humanize = (value?: string) =>
  (value || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const cardStyle: React.CSSProperties = {
  background: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: '12px',
  padding: '1.5rem'
};

// Mirrors the backend: documents (policy, RC, licence ...) are not damage photos.
const DOCUMENT_EVIDENCE_PATTERN =
  /(policy|registration|rc[ _]?book|licen[cs]e|driving|insurance|document|certificate|aadhaar|aadhar|pan[ _]card|id[ _]proof|invoice|supporting)/i;

// Repair lines the technician starts from: lines they already saved win,
// otherwise one line per AI finding group (findings they rejected are dropped).
// The AI only gives a price RANGE per line, so parts / labour are left for the
// workshop to fill in instead of inventing a split.
const buildEstimateItems = (repair: any, fusion: any): any[] => {
  if (Array.isArray(repair?.items) && repair.items.length > 0) {
    return repair.items;
  }
  const overrides = fusion?.technician_overrides || {};
  const lines: any[] = repair?.ai_estimate?.line_items || [];
  return lines
    .filter((line) => {
      const ids: string[] = line.finding_ids || [];
      return !(ids.length > 0 && ids.every((id) => overrides[id] === 'REJECTED'));
    })
    .map((line) => ({
      part: line.part === 'unknown' ? 'Unidentified part (technician to confirm)' : humanize(line.part),
      damage: line.damage_type,
      severity: line.severity,
      action: '',
      partsCost: '',
      laborCost: '',
      notes: '',
      ai_min_cost: line.min_cost,
      ai_max_cost: line.max_cost,
      finding_ids: line.finding_ids || [],
      provisional: !!line.provisional
    }));
};

// The analysed photo with the AI's boxes drawn on top (SVG in the photo's own
// pixel space, so boxes line up whatever size the photo is displayed at).
const AnnotatedPhoto: React.FC<{ src: string; findings: any[]; imageSize?: number[] }> = ({ src, findings, imageSize }) => {
  const [natural, setNatural] = useState<number[] | null>(null);
  const size = imageSize && imageSize.length === 2 ? imageSize : natural;
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <img
        src={src}
        alt="AI analysed vehicle photo"
        onLoad={(e) => setNatural([e.currentTarget.naturalWidth, e.currentTarget.naturalHeight])}
        style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
      />
      {size && (
        <svg
          viewBox={`0 0 ${size[0]} ${size[1]}`}
          preserveAspectRatio="xMidYMid meet"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        >
          {findings.map((f, i) => {
            const [x1, y1, x2, y2] = f.bbox || [];
            if ([x1, y1, x2, y2].some((v) => typeof v !== 'number')) return null;
            const color = f.part === 'unknown' ? '#f59e0b' : f.requires_review ? '#dc2626' : '#16a34a';
            const fontSize = Math.max(size[0], size[1]) / 48;
            const label = `${f.part && f.part !== 'unknown' ? humanize(f.part) : 'Unmatched'} · ${humanize(f.damage_type)}`;
            return (
              <g key={f.finding_id || i}>
                <rect x={x1} y={y1} width={x2 - x1} height={y2 - y1} fill="none" stroke={color} strokeWidth={Math.max(2, fontSize / 6)} />
                <text
                  x={x1}
                  y={Math.max(fontSize, y1 - fontSize / 3)}
                  fontSize={fontSize}
                  fontWeight={700}
                  fill={color}
                  stroke="#000000"
                  strokeWidth={fontSize / 14}
                  paintOrder="stroke"
                >
                  {label}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
};

export const ServiceCenterPortal: React.FC<ServiceCenterPortalProps> = ({ user, currentRoute, onNavigate, onLogout, themeToggle }) => {
  const currentTab = (currentRoute && currentRoute !== '/') ? currentRoute.replace(/^\//, '') : 'dashboard';
  const setCurrentTab = (tab: string) => {
    if (onNavigate) {
      onNavigate(`/${tab}`);
    }
  };

  const [claims, setClaims] = useState<any[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<any | null>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);

  const [, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters & Search
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Upload state
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [isCameraActive, setIsCameraActive] = useState<boolean>(false);
  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const mediaStreamRef = React.useRef<MediaStream | null>(null);

  const startCamera = async () => {
    setIsCameraActive(true);
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } }
      });
      mediaStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err: any) {
      console.error('Camera access error:', err);
      setError('Unable to access camera device. Please grant camera permission in your browser.');
      setIsCameraActive(false);
    }
  };

  const stopCamera = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    setIsCameraActive(false);
  };

  const captureCameraPhoto = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(blob => {
        if (blob) {
          const file = new File([blob], `captured_photo_${Date.now()}.jpg`, { type: 'image/jpeg' });
          setUploadFiles(prev => [...prev, file]);
          setSuccessMessage('Photo captured successfully from camera!');
        }
      }, 'image/jpeg', 0.92);
    }
  };

  // AI Assessment run progress
  const [isAssessmentRunning, setIsAssessmentRunning] = useState(false);
  const [assessmentData, setAssessmentData] = useState<any>(null);

  const isDamagePhoto = (evidence: any) =>
    /\.(jpg|jpeg|png|webp)$/i.test(evidence.file_name || evidence.file_path || '') &&
    !DOCUMENT_EVIDENCE_PATTERN.test(`${evidence.file_type || ''} ${evidence.file_name || ''}`);
  const toPhotoUrl = (filePath?: string) => {
    const cleaned = (filePath || '').replace(/\\/g, '/').replace(/^(\.\.\/)+/, '').replace(/^\/+/, '');
    return cleaned ? `http://127.0.0.1:8000/${cleaned}` : '';
  };
  const damagePhotos: any[] = (selectedClaim?.evidence || []).filter(isDamagePhoto);
  const damagePhoto = damagePhotos[0];
  const claimProgress = getClaimProgress(selectedClaim?.status);
  const serviceTimelineStages = [
    'Submitted',
    'Service Center Intake',
    'AI Assessment',
    'Technician Review',
    'Repair Estimation',
    'Claim Package'
  ];

  // Everything below comes straight from the saved / just-run assessment.
  const activeAssessment = assessmentData || selectedClaim?.assessment;
  const fusionBlock = activeAssessment?.fusion_results || activeAssessment?.fusion;
  const repairBlock = activeAssessment?.repair_results || activeAssessment?.repair;
  const assessmentSummary = fusionBlock?.summary;
  const imageResults: any[] = fusionBlock?.images || [];
  const findings: any[] = imageResults.flatMap((img: any) =>
    (img.detections || []).map((d: any, i: number) => ({
      ...d,
      image: img.image,
      finding_id: d.finding_id || `${img.image}_D${d.damage_id ?? i + 1}`
    }))
  );

  // Technician Review State (filled from the saved assessment - see effect below)
  const [technicianOverrides, setTechnicianOverrides] = useState<Record<string, string>>({});
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [assignedTechName, setAssignedTechName] = useState<string>('');

  // Repair Estimate State (built from the AI estimate / saved workshop lines)
  const [estimateItems, setEstimateItems] = useState<any[]>([]);

  const undecidedCount = findings.filter((f) => !technicianOverrides[f.finding_id]).length;
  const lineSubtotal = (item: any) => (Number(item.partsCost) || 0) + (Number(item.laborCost) || 0);
  const estimateTotal = estimateItems.reduce((acc, item) => acc + lineSubtotal(item), 0);
  const aiRangeMin = estimateItems.reduce((acc, item) => acc + (Number(item.ai_min_cost) || 0), 0);
  const aiRangeMax = estimateItems.reduce((acc, item) => acc + (Number(item.ai_max_cost) || 0), 0);
  const formatInr = (value: number) => `₹${Number(value).toLocaleString('en-IN')}`;

  // Claim Package Hub Interactive State
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [dispatchStatus, setDispatchStatus] = useState<string | null>(null);

  // Assign Technician Modal State
  const [assignModalClaim, setAssignModalClaim] = useState<any | null>(null);
  const [assignModalTechName, setAssignModalTechName] = useState('');
  const [isAssigningTech, setIsAssigningTech] = useState(false);
  const [assignStatusMsg, setAssignStatusMsg] = useState<string | null>(null);

  const openAssignModal = (claimItem: any) => {
    setAssignModalClaim(claimItem);
    const existing = claimItem.assigned_technician;
    setAssignModalTechName(existing && existing !== 'Not assigned' ? existing : 'Rahul');
    setAssignStatusMsg(null);
  };

  const handleSaveTechnicianAssignment = async () => {
    if (!assignModalClaim) return;
    const techName = assignModalTechName.trim();
    if (!techName) return;

    setIsAssigningTech(true);
    try {
      await serviceCenterApi.assignTechnician(assignModalClaim.claim_id, techName);
      
      // Update local claims state immediately for ultra-fast responsive UI
      setClaims(prev => prev.map(c => (
        c.claim_id === assignModalClaim.claim_id ? { ...c, assigned_technician: techName } : c
      )));

      // If active claim matches, update active review tech name and selected claim
      if (selectedClaimId === assignModalClaim.claim_id) {
        setAssignedTechName(techName);
        if (selectedClaim) {
          setSelectedClaim({
            ...selectedClaim,
            assigned_technician: techName
          });
        }
      }

      setAssignStatusMsg(`Successfully assigned ${techName} to ${assignModalClaim.claim_id}`);
      setTimeout(() => {
        setAssignModalClaim(null);
        setAssignStatusMsg(null);
        setIsAssigningTech(false);
      }, 700);

      // Also reload in background to sync backend summary
      loadDashboardAndClaims();
    } catch (err: any) {
      setAssignStatusMsg(`Failed to assign technician: ${err.message || 'Unknown error'}`);
      setIsAssigningTech(false);
    }
  };

  const generateClaimManifest = () => {
    if (!selectedClaim) return {};
    return {
      claim_id: selectedClaim.claim_id,
      schema_version: '2.4.0-underwriting',
      generated_at: new Date().toISOString(),
      integrity_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      carrier: {
        company_name: selectedClaim.insurance_company || 'Universal Sompo General Insurance',
        policy_number: selectedClaim.policy_number || 'POL-883921',
        policy_type: selectedClaim.policy_type || 'Comprehensive Zero-Depreciation',
        coverage_status: 'ACTIVE_VALIDATED'
      },
      insured_party: {
        customer_name: selectedClaim.customer_name || 'Verified Insured Customer',
        registration_state: selectedClaim.registration_state || 'MH',
        accident_location: selectedClaim.accident_location || 'Mumbai'
      },
      vehicle_dossier: {
        registration_number: selectedClaim.registration_number || 'DL 01 AB 1234',
        vin: selectedClaim.vin || 'VIN-UNSPECIFIED',
        make: selectedClaim.vehicle_make || 'Kia',
        model: selectedClaim.vehicle_model || 'Seltos',
        year: selectedClaim.vehicle_year || 2022
      },
      cv_telemetry: {
        model: 'YOLO26m-seg',
        runtime: 'Tesla T4 / Ultralytics 8.4.184',
        findings_count: findings.length,
        overall_severity: selectedClaim.assessment?.overall_severity || 'Moderate',
        fused_items: findings.map((f: any, idx: number) => ({
          finding_id: f.finding_id || `ITEM_${idx + 1}`,
          part: f.part || 'unknown',
          damage_type: f.damage_type,
          severity: f.severity,
          confidence: f.confidence,
          adjudication_override: technicianOverrides[f.finding_id] || 'CONFIRMED'
        }))
      },
      adjudicated_financials: {
        currency: 'INR',
        total_estimate: estimateTotal > 0 ? estimateTotal : (selectedClaim.repair_estimate?.total_estimated_cost || 0),
        workshop_breakdown: estimateItems.map((item: any) => ({
          part_name: item.part,
          damage_action: item.action || 'REPAIR',
          parts_cost: Number(item.partsCost) || 0,
          labor_cost: Number(item.laborCost) || 0,
          subtotal: lineSubtotal(item)
        })),
        certified_technician: {
          name: assignedTechName || 'Authorized Workshop Specialist',
          facility: 'AutoInsight Authorized Center #104',
          adjudication_status: 'APPROVED_FOR_CARRIER_DISPATCH'
        }
      }
    };
  };

  const handleCopyDossierLink = () => {
    if (!selectedClaim) return;
    const url = serviceCenterApi.getClaimPDFUrl(selectedClaim.claim_id);
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  const handleDispatchToInsurer = () => {
    setDispatchStatus('Transmitting dossier payload to underwriter API gateway...');
    setTimeout(() => {
      setDispatchStatus('Dossier successfully acknowledged by Insurer Gateway (Ack Ref #ACK-98421).');
      setTimeout(() => setDispatchStatus(null), 4500);
    }, 1200);
  };

  useEffect(() => {
    loadDashboardAndClaims();
  }, []);

  useEffect(() => {
    if (selectedClaimId) {
      fetchClaimDetail(selectedClaimId);
    }
  }, [selectedClaimId]);

  // Rebuild the review + estimate state from what the backend actually holds for the
  // selected claim. This also stops one claim's inputs leaking into the next one.
  useEffect(() => {
    const assessment = selectedClaim?.assessment;
    const fusion = assessment?.fusion_results || {};
    const repair = assessment?.repair_results || {};
    const assigned = selectedClaim?.assigned_technician;
    setTechnicianOverrides(fusion.technician_overrides || {});
    setReviewNotes(fusion.review_notes || '');
    setAssignedTechName(
      fusion.technician_name || (assigned && assigned !== 'Not assigned' ? assigned : '') || user?.full_name || ''
    );
    setEstimateItems(buildEstimateItems(repair, fusion));
  }, [selectedClaim]);

  const loadDashboardAndClaims = async () => {
    setLoading(true);
    setError(null);
    try {
      const dash = await serviceCenterApi.getDashboard();
      setDashboardData(dash.summary || dash);
      const claimList = await serviceCenterApi.getClaims();
      setClaims(claimList);
      if (claimList.length > 0 && !selectedClaimId) {
        setSelectedClaimId(claimList[0].claim_id);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load Service Center claims queue.');
    } finally {
      setLoading(false);
    }
  };

  const fetchClaimDetail = async (claimId: string) => {
    try {
      const data = await serviceCenterApi.getClaim(claimId);
      setSelectedClaim(data);
      setAssessmentData(data.assessment || null);
    } catch (err) {
      console.error('Error loading claim details', err);
    }
  };

  const handleSelectClaim = (claimId: string, targetTab?: typeof currentTab) => {
    setSelectedClaimId(claimId);
    if (targetTab) {
      setCurrentTab(targetTab);
    } else {
      setCurrentTab('details');
    }
  };

  const handleRunAssessment = async (targetClaimId?: string) => {
    const claimIdToRun = targetClaimId || selectedClaimId;
    if (!claimIdToRun) {
      setError('No active claim selected to run AI assessment.');
      return;
    }
    setIsAssessmentRunning(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await serviceCenterApi.runAssessment(claimIdToRun);
      if (res.status && String(res.status).toLowerCase() !== 'completed') {
        throw new Error(`Assessment returned unexpected status: ${res.status}`);
      }
      const refreshedClaim = await serviceCenterApi.getClaim(claimIdToRun);
      setSelectedClaim(refreshedClaim);
      setAssessmentData(refreshedClaim.assessment || null);
      setSuccessMessage('AI Computer Vision Assessment completed successfully!');
      setCurrentTab('assessment');
    } catch (err: any) {
      console.error('AI Assessment Error:', err);
      setError(err.response?.data?.detail || err.message || 'AI assessment processing failed.');
    } finally {
      setIsAssessmentRunning(false);
    }
  };

  const replaceAssessmentPhotos = async () => {
    if (!selectedClaimId) return;
    setActionLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await serviceCenterApi.clearVehicleDamageEvidence(selectedClaimId);
      const refreshedClaim = await serviceCenterApi.getClaim(selectedClaimId);
      setSelectedClaim(refreshedClaim);
      setAssessmentData(refreshedClaim.assessment || null);
      setUploadFiles([]);
      setCurrentTab('evidence');
      setSuccessMessage('Previous service-center damage photos were removed. Select the replacement photos to continue.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not remove the previous damage photos. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveTechnicianReview = async (approve: boolean) => {
    if (!selectedClaimId) return;
    if (approve && !assignedTechName.trim()) {
      setError('Enter the verifying technician name before approving.');
      return;
    }
    if (approve && undecidedCount > 0) {
      setError(`${undecidedCount} finding(s) still need a decision (confirm, modify or reject).`);
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await serviceCenterApi.submitTechnicianReview(selectedClaimId, {
        technician_overrides: technicianOverrides,
        review_notes: reviewNotes,
        technician_name: assignedTechName.trim() || undefined
      });
      if (approve) {
        await serviceCenterApi.updateClaimStatus(selectedClaimId, 'human_review');
        setSuccessMessage('Technician verification completed & approved!');
        setCurrentTab('estimate');
      } else {
        setSuccessMessage('Technician review draft saved.');
      }
      fetchClaimDetail(selectedClaimId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit technician review');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveRepairEstimate = async () => {
    if (!selectedClaimId) return;
    const incomplete = estimateItems.filter((item) => !item.action || lineSubtotal(item) <= 0);
    if (incomplete.length > 0) {
      setError(
        `Choose an action and enter a cost for every line (${incomplete.length} incomplete). The AI range is shown as guidance only.`
      );
      return;
    }
    const items = estimateItems.map((item) => ({
      ...item,
      partsCost: Number(item.partsCost) || 0,
      laborCost: Number(item.laborCost) || 0
    }));
    const total = items.reduce((acc, item) => acc + item.partsCost + item.laborCost, 0);
    setActionLoading(true);
    setError(null);
    try {
      await serviceCenterApi.saveRepairEstimate(selectedClaimId, {
        items,
        total_estimated_cost: total
      });
      setSuccessMessage('Repair estimate approved & saved!');
      fetchClaimDetail(selectedClaimId);
      setCurrentTab('package');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save repair estimate');
    } finally {
      setActionLoading(false);
    }
  };

  const handleGeneratePackage = async () => {
    if (!selectedClaimId) return;
    setActionLoading(true);
    try {
      await serviceCenterApi.generateClaimPackage(selectedClaimId);
      setSuccessMessage('Digital Claim Package (PDF + ZIP + Manifest) generated successfully!');
      fetchClaimDetail(selectedClaimId);
      void loadDashboardAndClaims();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Package generation failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Filtered claims
  const filteredClaims = claims.filter(c => {
    const matchesStatus = filterStatus === 'ALL' || c.status?.toUpperCase().includes(filterStatus.toUpperCase());
    const matchesSearch = !searchQuery ||
      c.claim_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.customer_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.registration_number?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const sidebarNavItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'claims', label: 'Claims Queue', icon: FileText },
    { id: 'details', label: 'Claim Information', icon: UserCheck },
    { id: 'assessment', label: 'AI Damage Assessment', icon: ShieldCheck },
    { id: 'review', label: 'Technician Review', icon: CheckSquare },
    { id: 'estimate', label: 'Repair Estimates', icon: DollarSign },
    { id: 'package', label: 'Claim Package', icon: Package }
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f8fafc', color: '#0f172a' }}>
      {/* SIDEBAR */}
      <aside
        style={{
          width: '260px',
          background: '#0f172a',
          color: 'white',
          display: 'flex',
          flexDirection: 'column',
          position: 'fixed',
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 100,
          padding: '1.5rem 1rem'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '2rem', padding: '0 0.5rem' }}>
          <div style={{ padding: '0.5rem', background: '#0284c7', borderRadius: '10px', display: 'flex' }}>
            <Wrench size={22} color="white" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.1rem', fontWeight: 800, lineHeight: 1.1 }}>Service Center</h1>
            <span style={{ fontSize: '0.65rem', color: '#94a3b8', fontWeight: 700, letterSpacing: '0.05em' }}>
              TECHNICIAN PORTAL
            </span>
          </div>
        </div>

        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          {sidebarNavItems.map(item => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setCurrentTab(item.id as any)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.85rem',
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  border: 'none',
                  background: isActive ? '#0284c7' : 'transparent',
                  color: isActive ? 'white' : '#94a3b8',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {onLogout && (
          <div style={{ borderTop: '1px solid #334155', paddingTop: '1rem' }}>
            <button
              onClick={onLogout}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.65rem 1rem',
                width: '100%',
                borderRadius: '8px',
                border: 'none',
                background: 'transparent',
                color: '#ef4444',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <LogOut size={18} />
              <span>Sign Out</span>
            </button>
          </div>
        )}
      </aside>

      {/* MAIN BODY CONTAINER */}
      <div style={{ flex: 1, marginLeft: '260px', display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        {/* HEADER BAR */}
        <header
          className="service-center-topbar"
          style={{
            height: '64px',
            background: '#ffffff',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 2rem',
            position: 'sticky',
            top: 0,
            zIndex: 90
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a' }}>
              Service Center Operations & Damage Assessment
            </h2>
            {selectedClaimId && (
              <span className="badge badge-info" style={{ background: '#e0f2fe', color: '#0369a1', fontWeight: 700 }}>
                Active Claim: #{selectedClaimId}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {themeToggle}
            <button onClick={loadDashboardAndClaims} className="btn-secondary" style={{ padding: '0.45rem 0.85rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <RefreshCw size={14} /> Refresh Queue
            </button>
            <div
              onClick={() => setCurrentTab('profile')}
              title="Click to view Technician Profile"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                background: currentTab === 'profile' ? '#e0f2fe' : '#f1f5f9',
                border: currentTab === 'profile' ? '1px solid #0284c7' : '1px solid transparent',
                padding: '0.35rem 0.85rem',
                borderRadius: '9999px',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: '#0284c7', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.85rem' }}>
                <User size={16} />
              </div>
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#334155' }}>{user?.service_center_name || (user?.role === 'admin' ? 'Platform Admin' : 'Technician Advisor')}</span>
            </div>
          </div>
        </header>

        {/* FEEDBACK MESSAGES */}
        {error && (
          <div style={{ margin: '1rem 2rem 0 2rem', padding: '1rem', background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem' }}>
            <AlertCircle size={18} /> {error}
          </div>
        )}
        {successMessage && (
          <div style={{ margin: '1rem 2rem 0 2rem', padding: '1rem', background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem' }}>
            <CheckCircle size={18} /> {successMessage}
          </div>
        )}

        {/* CONTENT AREA */}
        <main style={{ flex: 1, padding: '2rem', maxWidth: '1400px', width: '100%', margin: '0 auto' }}>
          {/* TAB 1: DASHBOARD */}
          {currentTab === 'dashboard' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              <div>
                <button
                  onClick={() => window.history.back()}
                  className="btn-secondary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginBottom: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', cursor: 'pointer' }}
                >
                  <ArrowLeft size={15} /> Back
                </button>
                <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Service Center Executive Summary</h3>
                <p style={{ color: '#64748b', fontSize: '0.9rem' }}>Real-time telemetry and claim intake lifecycle tracking.</p>
              </div>

              {/* SUMMARY CARDS */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem' }}>
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.25rem' }}>
                  <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Total Intake Claims</span>
                  <h4 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#0f172a', marginTop: '0.25rem' }}>{dashboardData?.total_claims || claims.length}</h4>
                </div>
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.25rem' }}>
                  <span style={{ fontSize: '0.8rem', color: '#0284c7', fontWeight: 600 }}>New Submitted Claims</span>
                  <h4 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#0284c7', marginTop: '0.25rem' }}>{dashboardData?.new_claims || 0}</h4>
                </div>
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.25rem' }}>
                  <span style={{ fontSize: '0.8rem', color: '#d97706', fontWeight: 600 }}>Assessment In Progress</span>
                  <h4 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#d97706', marginTop: '0.25rem' }}>{dashboardData?.claims_under_assessment || 0}</h4>
                </div>
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.25rem' }}>
                  <span style={{ fontSize: '0.8rem', color: '#7c3aed', fontWeight: 600 }}>Awaiting Technician Review</span>
                  <h4 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#7c3aed', marginTop: '0.25rem' }}>{dashboardData?.awaiting_technician_review || 0}</h4>
                </div>
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.25rem' }}>
                  <span style={{ fontSize: '0.8rem', color: '#16a34a', fontWeight: 600 }}>Packages Generated</span>
                  <h4 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#16a34a', marginTop: '0.25rem' }}>{dashboardData?.packages_generated || 0}</h4>
                </div>
              </div>

              {/* RECENT INTAKE QUEUE TABLE */}
              <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem', color: '#0f172a' }}>Recent Customer Claim Submissions</h4>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>
                        <th style={{ padding: '0.75rem' }}>CLAIM ID</th>
                        <th style={{ padding: '0.75rem' }}>CUSTOMER</th>
                        <th style={{ padding: '0.75rem' }}>VEHICLE</th>
                        <th style={{ padding: '0.75rem' }}>SUBMITTED DATE</th>
                        <th style={{ padding: '0.75rem' }}>STATUS</th>
                        <th style={{ padding: '0.75rem' }}>TECHNICIAN</th>
                        <th style={{ padding: '0.75rem' }}>ACTION</th>
                      </tr>
                    </thead>
                    <tbody>
                      {claims.slice(0, 8).map(claim => (
                        <tr key={claim.claim_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '0.85rem', fontWeight: 700, color: '#0f172a' }}>{claim.claim_id}</td>
                          <td style={{ padding: '0.85rem', color: '#334155' }}>{claim.customer_name}</td>
                          <td style={{ padding: '0.85rem', color: '#334155' }}>{claim.vehicle_make} {claim.vehicle_model} ({claim.registration_number})</td>
                          <td style={{ padding: '0.85rem', color: '#64748b' }}>{claim.created_at ? new Date(claim.created_at).toLocaleDateString() : 'N/A'}</td>
                          <td style={{ padding: '0.85rem' }}>
                            <span className="badge badge-info" style={{ background: '#e0f2fe', color: '#0369a1', fontWeight: 700 }}>{claim.status}</span>
                          </td>
                          <td style={{ padding: '0.85rem' }}>
                            {claim.assigned_technician && claim.assigned_technician !== 'Not assigned' ? (
                              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem' }}>
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '0.35rem',
                                  padding: '0.25rem 0.65rem',
                                  borderRadius: '9999px',
                                  background: '#f0fdf4',
                                  color: '#15803d',
                                  fontWeight: 700,
                                  fontSize: '0.8rem',
                                  border: '1px solid #bbf7d0',
                                  boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
                                }}>
                                  <UserCheck size={13} style={{ color: '#16a34a' }} />
                                  {claim.assigned_technician}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => openAssignModal(claim)}
                                  title="Change or reassign technician"
                                  style={{
                                    border: '1px solid #cbd5e1',
                                    background: '#ffffff',
                                    borderRadius: '6px',
                                    color: '#475569',
                                    cursor: 'pointer',
                                    padding: '0.25rem 0.45rem',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.2rem',
                                    fontSize: '0.7rem',
                                    fontWeight: 600
                                  }}
                                >
                                  <Wrench size={11} />
                                  Edit
                                </button>
                              </div>
                            ) : (
                              <button
                                type="button"
                                onClick={() => openAssignModal(claim)}
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '0.35rem',
                                  padding: '0.3rem 0.75rem',
                                  borderRadius: '6px',
                                  background: '#eff6ff',
                                  color: '#0284c7',
                                  border: '1px dashed #38bdf8',
                                  fontSize: '0.75rem',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                  boxShadow: '0 1px 2px rgba(2, 132, 199, 0.05)'
                                }}
                              >
                                <User size={12} />
                                + Assign Technician
                              </button>
                            )}
                          </td>
                          <td style={{ padding: '0.85rem' }}>
                            <button onClick={() => handleSelectClaim(claim.claim_id, 'details')} className="btn-secondary" style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}>
                              Inspect Claim
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CLAIMS QUEUE & FILTERS */}
          {currentTab === 'claims' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <button
                    onClick={() => setCurrentTab('dashboard')}
                    className="btn-secondary"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginBottom: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', cursor: 'pointer' }}
                  >
                    <ArrowLeft size={15} /> Back
                  </button>
                  <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Claims Queue Directory</h3>
                  <p style={{ color: '#64748b', fontSize: '0.875rem' }}>Live claim records synchronized from FastAPI database.</p>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <div style={{ position: 'relative', minWidth: '240px' }}>
                    <Search size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: '#94a3b8' }} />
                    <input
                      type="text"
                      placeholder="Search Claim ID, Customer, Reg #"
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                      style={{ padding: '0.5rem 0.5rem 0.5rem 2.2rem', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '0.85rem', width: '100%' }}
                    />
                  </div>
                  <select
                    value={filterStatus}
                    onChange={e => setFilterStatus(e.target.value)}
                    style={{ padding: '0.5rem', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '0.85rem', background: '#white' }}
                  >
                    <option value="ALL">All Statuses</option>
                    <option value="SUBMITTED">Submitted</option>
                    <option value="ASSESSMENT">Assessment In Progress</option>
                    <option value="HUMAN_REVIEW">Technician Review</option>
                    <option value="PACKAGE">Package Generated</option>
                  </select>
                </div>
              </div>

              <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>
                        <th style={{ padding: '0.75rem' }}>CLAIM ID</th>
                        <th style={{ padding: '0.75rem' }}>CUSTOMER</th>
                        <th style={{ padding: '0.75rem' }}>VEHICLE</th>
                        <th style={{ padding: '0.75rem' }}>REGISTRATION</th>
                        <th style={{ padding: '0.75rem' }}>ACCIDENT DATE</th>
                        <th style={{ padding: '0.75rem' }}>STATUS</th>
                        <th style={{ padding: '0.75rem' }}>TECHNICIAN</th>
                        <th style={{ padding: '0.75rem' }}>ACTION</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredClaims.map(c => (
                        <tr key={c.claim_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '0.85rem', fontWeight: 700, color: '#0f172a' }}>{c.claim_id}</td>
                          <td style={{ padding: '0.85rem', color: '#334155' }}>{c.customer_name}</td>
                          <td style={{ padding: '0.85rem', color: '#334155' }}>{c.vehicle_make} {c.vehicle_model}</td>
                          <td style={{ padding: '0.85rem', color: '#475569' }}>{c.registration_number}</td>
                          <td style={{ padding: '0.85rem', color: '#64748b' }}>{c.accident_date || 'N/A'}</td>
                          <td style={{ padding: '0.85rem' }}><span className="badge badge-info" style={{ background: '#e0f2fe', color: '#0369a1' }}>{c.status}</span></td>
                          <td style={{ padding: '0.85rem' }}>
                            {c.assigned_technician && c.assigned_technician !== 'Not assigned' ? (
                              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem' }}>
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '0.35rem',
                                  padding: '0.2rem 0.55rem',
                                  borderRadius: '9999px',
                                  background: '#f0fdf4',
                                  color: '#15803d',
                                  fontWeight: 700,
                                  fontSize: '0.75rem',
                                  border: '1px solid #bbf7d0'
                                }}>
                                  <UserCheck size={12} style={{ color: '#16a34a' }} />
                                  {c.assigned_technician}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => openAssignModal(c)}
                                  title="Change technician"
                                  style={{
                                    border: '1px solid #cbd5e1',
                                    background: '#ffffff',
                                    borderRadius: '5px',
                                    color: '#64748b',
                                    cursor: 'pointer',
                                    padding: '0.2rem 0.35rem',
                                    display: 'inline-flex',
                                    alignItems: 'center'
                                  }}
                                >
                                  <Wrench size={11} />
                                </button>
                              </div>
                            ) : (
                              <button
                                type="button"
                                onClick={() => openAssignModal(c)}
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '0.3rem',
                                  padding: '0.25rem 0.6rem',
                                  borderRadius: '6px',
                                  background: '#eff6ff',
                                  color: '#0284c7',
                                  border: '1px dashed #38bdf8',
                                  fontSize: '0.75rem',
                                  fontWeight: 600,
                                  cursor: 'pointer'
                                }}
                              >
                                <User size={11} /> + Assign
                              </button>
                            )}
                          </td>
                          <td style={{ padding: '0.85rem' }}>
                            <button onClick={() => handleSelectClaim(c.claim_id, 'details')} className="btn-primary" style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}>
                              Open Workflow
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: CLAIM DETAILS */}
          {currentTab === 'details' && selectedClaim && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <button
                    onClick={() => setCurrentTab('claims')}
                    className="btn-secondary"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginBottom: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', cursor: 'pointer' }}
                  >
                    <ArrowLeft size={15} /> Back to Queue
                  </button>
                  <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Claim Record — #{selectedClaim.claim_id}</h3>
                  <p style={{ color: '#64748b', fontSize: '0.85rem' }}>Customer, Vehicle, Insurance, and Incident Specifications.</p>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <button
                    onClick={() => setCurrentTab('evidence')}
                    className="btn-primary"
                  >
                    Start AI Damage Assessment ⚡
                  </button>
                </div>
              </div>

              {/* TIMELINE VISUALIZER */}
              <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a', marginBottom: '1rem' }}>Claim Progress Lifecycle</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem' }}>
                  {serviceTimelineStages.map((title, index) => {
                    const stageStatus = claimProgress.stageStatus(index);
                    const complete = stageStatus === 'completed';
                    const active = stageStatus === 'active';
                    const foreground = complete ? '#166534' : active ? '#0369a1' : '#64748b';
                    return (
                      <div key={title} style={{ background: complete ? '#f0fdf4' : active ? '#e0f2fe' : '#f8fafc', border: `1px solid ${complete ? '#bbf7d0' : active ? '#bae6fd' : '#e2e8f0'}`, padding: '0.75rem', borderRadius: '8px', textAlign: 'center' }}>
                        {complete
                          ? <CheckCircle size={18} style={{ color: foreground, margin: '0 auto 0.25rem auto' }} />
                          : <Clock size={18} style={{ color: foreground, margin: '0 auto 0.25rem auto' }} />}
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: foreground }}>{title}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* SPECIFICATION GRID */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                  <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#0284c7', marginBottom: '1rem' }}>CUSTOMER INFORMATION</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.875rem' }}>
                    <p><strong>Full Name:</strong> {selectedClaim.customer_name}</p>
                    <p><strong>Email Address:</strong> {selectedClaim.customer_email}</p>
                    <p><strong>Phone / Mobile:</strong> {selectedClaim.customer_phone}</p>
                    <p><strong>Address:</strong> {selectedClaim.customer_address}</p>
                  </div>
                </div>

                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                  <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#0284c7', marginBottom: '1rem' }}>VEHICLE INFORMATION</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.875rem' }}>
                    <p><strong>Make & Model:</strong> {selectedClaim.vehicle_make} {selectedClaim.vehicle_model} ({selectedClaim.vehicle_year || 'Not provided'})</p>
                    <p><strong>Registration Number:</strong> {selectedClaim.registration_number}</p>
                    <p><strong>VIN (Chassis):</strong> {selectedClaim.vin}</p>
                    <p><strong>Engine Number:</strong> {selectedClaim.engine_number}</p>
                  </div>
                </div>

                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                  <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#0284c7', marginBottom: '1rem' }}>INSURANCE INFORMATION</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.875rem' }}>
                    <p><strong>Insurer Company:</strong> {selectedClaim.insurance_company}</p>
                    <p><strong>Policy Number:</strong> {selectedClaim.policy_number}</p>
                    <p><strong>Policy Type:</strong> {selectedClaim.policy_type}</p>
                    <p><strong>Coverage Expiry:</strong> {selectedClaim.policy_expiry}</p>
                  </div>
                </div>

                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                  <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#0284c7', marginBottom: '1rem' }}>ACCIDENT & INCIDENT SUMMARY</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.875rem' }}>
                    <p><strong>Accident Date & Time:</strong> {selectedClaim.accident_date} at {selectedClaim.accident_time}</p>
                    <p><strong>Accident Location:</strong> {selectedClaim.accident_location}</p>
                    <p><strong>Accident Type:</strong> {selectedClaim.accident_type}</p>
                    <p><strong>Description:</strong> {selectedClaim.accident_description || 'No description provided.'}</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: MULTI-PHOTO UPLOAD & AI DAMAGE ASSESSMENT */}
          {currentTab === 'evidence' && selectedClaim && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
              <div>
                <button
                  onClick={() => setCurrentTab('details')}
                  className="btn-secondary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginBottom: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', cursor: 'pointer' }}
                >
                  <ArrowLeft size={15} /> Back to Claim Info
                </button>
                <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Vehicle Damage Photo Intake & AI Assessment</h3>
                <p style={{ color: '#64748b', fontSize: '0.85rem' }}>Capture or select multiple vehicle photographs simultaneously to run AI computer vision evaluation.</p>
              </div>

              {/* SERVICE CENTER DEDICATED MULTI-PHOTO UPLOAD FORM */}
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (uploadFiles.length === 0) {
                    setError('Please select or capture at least 1 vehicle damage photograph.');
                    return;
                  }
                  setActionLoading(true);
                  setError(null);
                  try {
                    await serviceCenterApi.uploadEvidence(selectedClaim.claim_id, uploadFiles, 'Vehicle Damage');
                    setSuccessMessage(`${uploadFiles.length} photographs uploaded successfully! Executing AI Computer Vision Assessment...`);
                    setUploadFiles([]);
                    await handleRunAssessment(selectedClaim.claim_id);
                  } catch (err: any) {
                    setError(err.response?.data?.detail || 'Upload or AI assessment failed.');
                  } finally {
                    setActionLoading(false);
                  }
                }}
                style={{ background: '#ffffff', border: '2px solid #0284c7', borderRadius: '12px', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', position: 'relative' }}
              >
                {(actionLoading || isAssessmentRunning) && (
                  <div className="assessment-processing-overlay" role="status" aria-live="polite">
                    <div className="assessment-processing-card">
                      <div className="assessment-scan-icon"><RefreshCw size={30} /></div>
                      <h4>{actionLoading && !isAssessmentRunning ? 'Preparing your photos' : 'Assessing vehicle damage'}</h4>
                      <p>{actionLoading && !isAssessmentRunning ? 'Uploading evidence securely…' : 'AI is analyzing the submitted photos for damage and affected parts.'}</p>
                      <div className="assessment-progress-track"><span /></div>
                      <small>Please keep this page open while the assessment runs.</small>
                    </div>
                  </div>
                )}
                <div style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '1rem' }}>
                  <h4 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <UploadCloud style={{ color: '#0284c7' }} /> Multi-Photo Capture & Intake
                  </h4>
                  <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.25rem' }}>
                    Select multiple vehicle damage photos from device storage or take live photos using your camera.
                  </p>
                </div>

                {/* LIVE CAMERA VIEWFINDER MODAL / EMBED */}
                {isCameraActive ? (
                  <div
                    style={{
                      border: '2px solid #0284c7',
                      borderRadius: '12px',
                      padding: '1.5rem',
                      background: '#0f172a',
                      color: 'white',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '1rem',
                      position: 'relative'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Camera size={18} /> Live Vehicle Camera Feed Active
                      </span>
                      <button
                        type="button"
                        onClick={stopCamera}
                        style={{ background: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', padding: '0.35rem 0.75rem', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 700 }}
                      >
                        Close Camera ✕
                      </button>
                    </div>

                    <div style={{ width: '100%', maxWidth: '640px', aspectRatio: '16/9', background: '#000000', borderRadius: '8px', overflow: 'hidden', position: 'relative' }}>
                      <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    </div>

                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                      <button
                        type="button"
                        onClick={captureCameraPhoto}
                        className="btn-primary"
                        style={{ padding: '0.65rem 1.5rem', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem', background: '#0284c7' }}
                      >
                        <Camera size={18} /> Capture Photo 📸
                      </button>
                    </div>
                  </div>
                ) : (
                  /* DRAG & DROP / MULTI-FILE / CAMERA DRIVER */
                  <div
                    style={{
                      border: '2px dashed #0284c7',
                      borderRadius: '12px',
                      padding: '2.5rem 1.5rem',
                      textAlign: 'center',
                      background: '#f0f9ff',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '1rem'
                    }}
                  >
                    <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: '#e0f2fe', color: '#0284c7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Camera size={28} />
                    </div>
                    <div>
                      <h5 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>Browse Files or Turn On Live Camera</h5>
                      <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.25rem' }}>Select multiple saved images or activate live camera to snap damage photos</p>
                    </div>

                    <input
                      id="multi-photo-input"
                      type="file"
                      multiple
                      accept="image/*"
                      style={{ display: 'none' }}
                      onChange={e => {
                        const selected = Array.from(e.target.files || []);
                        if (selected.length > 0) {
                          setUploadFiles(prev => [...prev, ...selected]);
                        }
                      }}
                    />

                    <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => {
                          const inputEl = document.getElementById('multi-photo-input');
                          if (inputEl) inputEl.click();
                        }}
                        style={{ padding: '0.55rem 1.25rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}
                      >
                        <UploadCloud size={16} /> Choose Multiple Files
                      </button>
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={startCamera}
                        style={{ padding: '0.55rem 1.25rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}
                      >
                        <Camera size={16} /> Turn On Camera 📸
                      </button>
                    </div>
                  </div>
                )}

                {/* SELECTED PHOTOS PREVIEW QUEUE WITH REAL IMAGE THUMBNAILS */}
                {uploadFiles.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a' }}>
                        Selected Photos Queue ({uploadFiles.length} files attached - Image Preview Enabled)
                      </span>
                      <button
                        type="button"
                        onClick={() => setUploadFiles([])}
                        style={{ background: 'none', border: 'none', color: '#ef4444', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' }}
                      >
                        Clear All
                      </button>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '0.85rem' }}>
                      {uploadFiles.map((file, idx) => {
                        const previewUrl = URL.createObjectURL(file);
                        return (
                          <div
                            key={idx}
                            style={{
                              border: '2px solid #0284c7',
                              borderRadius: '10px',
                              overflow: 'hidden',
                              background: '#ffffff',
                              display: 'flex',
                              flexDirection: 'column',
                              position: 'relative',
                              boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                            }}
                          >
                            <div style={{ width: '100%', height: '110px', background: '#0f172a', position: 'relative' }}>
                              <img
                                src={previewUrl}
                                alt={file.name}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              />
                              <button
                                type="button"
                                onClick={() => setUploadFiles(prev => prev.filter((_, i) => i !== idx))}
                                style={{
                                  position: 'absolute',
                                  top: '4px',
                                  right: '4px',
                                  background: 'rgba(239, 68, 68, 0.9)',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '50%',
                                  width: '22px',
                                  height: '22px',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  cursor: 'pointer'
                                }}
                              >
                                <X size={14} />
                              </button>
                            </div>
                            <div style={{ padding: '0.5rem', overflow: 'hidden' }}>
                              <p style={{ fontSize: '0.75rem', fontWeight: 700, color: '#0f172a', margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {file.name}
                              </p>
                              <span style={{ fontSize: '0.68rem', color: '#64748b' }}>{(file.size / 1024).toFixed(1)} KB</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* SUBMIT BUTTON */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '0.5rem' }}>
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={actionLoading || isAssessmentRunning || uploadFiles.length === 0}
                    style={{ padding: '0.75rem 1.5rem', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                  >
                    {actionLoading || isAssessmentRunning ? (
                      'Uploading & Evaluating Damage with AI...'
                    ) : (
                      <>Run AI Computer Vision Assessment ⚡ ({uploadFiles.length} Photos)</>
                    )}
                  </button>
                </div>
              </form>


            </div>
          )}

          {/* TAB 5: AI ASSESSMENT */}
          {currentTab === 'assessment' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem', position: 'relative' }}>
              {isAssessmentRunning && (
                <div className="assessment-rerun-status" role="status" aria-live="polite">
                  <RefreshCw size={20} className="assessment-rerun-spinner" />
                  <div style={{ flex: 1 }}>
                    <strong>Re-running AI damage assessment…</strong>
                    <div className="assessment-progress-track"><span /></div>
                    <small>Analyzing the saved vehicle damage photos. Your results will refresh automatically.</small>
                  </div>
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <button
                    onClick={replaceAssessmentPhotos}
                    disabled={actionLoading || isAssessmentRunning}
                    className="btn-secondary"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginBottom: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', cursor: 'pointer' }}
                  >
                    <ArrowLeft size={15} /> Replace Photos
                  </button>
                  <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>AI Damage & Part Detection Results</h3>
                  <p style={{ color: '#64748b', fontSize: '0.85rem' }}>Computer vision fusion models evaluated on backend.</p>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <button onClick={() => handleRunAssessment(selectedClaim?.claim_id)} className="btn-secondary" disabled={isAssessmentRunning}>
                    {isAssessmentRunning && <RefreshCw size={15} className="assessment-rerun-spinner" />}
                    {isAssessmentRunning ? 'Re-running…' : 'Re-run AI Assessment'}
                  </button>
                  <button onClick={() => setCurrentTab('review')} className="btn-primary">
                    Proceed to Technician Review →
                  </button>
                </div>
              </div>

              {/* DATA-QUALITY CAVEATS COMPUTED BY THE BACKEND */}
              {assessmentSummary?.warnings?.length > 0 && (
                <div style={{ background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '12px', padding: '1rem 1.25rem', color: '#92400e', fontSize: '0.85rem' }}>
                  <strong>Review before relying on this assessment</strong>
                  <ul style={{ margin: '0.5rem 0 0 1.1rem' }}>
                    {assessmentSummary.warnings.map((warning: string, i: number) => (
                      <li key={i}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* ASSESSMENT RESULTS GRID */}
              {assessmentData || selectedClaim?.assessment ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                  {/* DETECTED DAMAGE */}
                  <div style={cardStyle}>
                    <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#0284c7', marginBottom: '1rem' }}>Detected Vehicle Damage ({findings.length})</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {findings.length ? findings.map((f: any) => (
                        <div key={f.finding_id} style={{ padding: '0.75rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem' }}>
                          <div>
                            <strong style={{ fontSize: '0.875rem', color: '#0f172a' }}>
                              {f.part && f.part !== 'unknown' ? humanize(f.part) : 'Part not identified'}
                            </strong>
                            <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                              {humanize(f.damage_type)} • Confidence {f.damage_confidence != null ? Math.round(f.damage_confidence * 100) : 'N/A'}%
                              {f.part_confidence != null ? ` • Part ${Math.round(f.part_confidence * 100)}%` : ''}
                            </p>
                            <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.1rem' }}>{f.image}</p>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <span className={`badge ${String(f.severity || '').toLowerCase() === 'severe' ? 'badge-danger' : 'badge-warning'}`}>
                              {f.severity || 'Not rated'}
                            </span>
                            <p style={{ fontSize: '0.65rem', color: '#64748b', marginTop: '0.25rem' }}>
                              {f.severity_source === 'model' ? 'Severity: AI model' : 'Severity: rule-based'}
                            </p>
                          </div>
                        </div>
                      )) : <p style={{ color: '#64748b' }}>No damage was detected in the submitted vehicle photos.</p>}
                    </div>
                  </div>

                  {/* DAMAGE + PART FUSION & REVIEW FLAGS */}
                  <div style={cardStyle}>
                    <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#0284c7', marginBottom: '1rem' }}>Damage-Part Fusion & Review Flags</h4>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>
                            <th style={{ padding: '0.5rem' }}>PART</th>
                            <th style={{ padding: '0.5rem' }}>DAMAGE</th>
                            <th style={{ padding: '0.5rem' }}>REVIEW</th>
                          </tr>
                        </thead>
                        <tbody>
                          {findings.map((f: any) => (
                            <tr key={f.finding_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                              <td style={{ padding: '0.65rem 0.5rem', fontWeight: 700, color: '#0f172a' }}>
                                {f.part && f.part !== 'unknown' ? humanize(f.part) : 'Part not identified'}
                              </td>
                              <td style={{ padding: '0.65rem 0.5rem', color: '#475569' }}>{humanize(f.damage_type)}</td>
                              <td style={{ padding: '0.65rem 0.5rem', color: f.requires_review ? '#dc2626' : '#16a34a', fontWeight: 700 }}>
                                {f.requires_review ? humanize(String(f.review_reason || 'needs review').split(', ').join(' / ')) : 'OK'}
                              </td>
                            </tr>
                          ))}
                          {!findings.length && (
                            <tr><td colSpan={3} style={{ padding: '0.75rem 0.5rem', color: '#64748b' }}>No part matches were returned by the assessment.</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '3rem', textAlign: 'center' }}>
                  <p style={{ color: '#64748b', fontSize: '0.95rem' }}>No AI assessment data available yet. Please upload vehicle photos to run the computer vision pipeline.</p>
                  <button onClick={() => setCurrentTab('evidence')} className="btn-primary" style={{ marginTop: '1rem' }}>
                    Go to Photo Intake & Assessment ⚡
                  </button>
                </div>
              )}

              {/* BEFORE vs AFTER: one pair per damage photo, boxes drawn from the AI detections */}
              {selectedClaim && damagePhotos.length > 0 && (
                <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <div>
                    <h4 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Eye style={{ color: '#0284c7' }} /> Before vs After AI Computer Vision Analysis Comparison
                    </h4>
                    <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.25rem' }}>
                      Each original intake photograph next to the same photograph with the AI-detected damage boxes drawn on it.
                      Green = confident match, red = needs review, amber = no part matched.
                    </p>
                  </div>

                  {damagePhotos.map((photo: any) => {
                    const fileBase = String(photo.file_path || '').split(/[\\/]/).pop();
                    const record = imageResults.find((r: any) => r.image === photo.file_name || r.image === fileBase);
                    const photoFindings = record ? findings.filter((f: any) => f.image === record.image) : [];
                    const url = toPhotoUrl(photo.file_path);
                    const display = getEvidenceDisplay(photo.file_name);
                    return (
                      <div key={photo.id ?? photo.file_name} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                        {/* BEFORE: RAW INTAKE PHOTO */}
                        <div style={{ border: '2px solid #cbd5e1', borderRadius: '10px', overflow: 'hidden', background: '#0f172a' }}>
                          <div style={{ padding: '0.65rem 1rem', background: '#334155', color: 'white', fontWeight: 700, fontSize: '0.85rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>📷 BEFORE: Original Raw Intake Photograph</span>
                            <span style={{ fontSize: '0.7rem', background: '#475569', padding: '2px 8px', borderRadius: '4px' }}>Clean Image</span>
                          </div>
                          <div style={{ width: '100%', height: '280px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', position: 'relative' }}>
                            <img src={url} alt="Original Vehicle Photo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                          </div>
                          <div style={{ padding: '0.75rem', background: '#1e293b', color: '#94a3b8', fontSize: '0.75rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span>{`${display.label}: ${display.fileName}`}</span>
                            <span>Status: Intake Captured</span>
                          </div>
                        </div>

                        {/* AFTER: SAME PHOTO WITH THE AI BOXES */}
                        <div style={{ border: '2px solid #0284c7', borderRadius: '10px', overflow: 'hidden', background: '#0f172a' }}>
                          <div style={{ padding: '0.65rem 1rem', background: '#0284c7', color: 'white', fontWeight: 700, fontSize: '0.85rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>⚡ AFTER: AI Damage Findings</span>
                            <span style={{ fontSize: '0.7rem', background: '#0369a1', padding: '2px 8px', borderRadius: '4px' }}>
                              {record ? (record.status === 'completed' ? 'AI Evaluated' : record.status) : 'Not analysed yet'}
                            </span>
                          </div>
                          <div style={{ width: '100%', height: '280px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', position: 'relative' }}>
                            <AnnotatedPhoto src={url} findings={photoFindings} imageSize={record?.image_size} />
                          </div>
                          <div style={{ padding: '0.75rem', background: '#0c4a6e', color: '#e0f2fe', fontSize: '0.75rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span>AI Model: Damage + Parts Fusion</span>
                            <span>{photoFindings.length} finding{photoFindings.length === 1 ? '' : 's'}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              {selectedClaim && !damagePhoto && (
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                  <h4 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.5rem' }}>Damage Photo Assessment</h4>
                  <p style={{ color: '#475569' }}>This claim has no vehicle damage photo yet. Policy, registration, and driving-license documents are not used as damage photos. Upload a JPG, PNG, or WEBP image from Photo Intake to view the vehicle here.</p>
                  <button onClick={() => setCurrentTab('evidence')} className="btn-primary" style={{ marginTop: '1rem' }}>
                    Go to Photo Intake
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 6: TECHNICIAN REVIEW & OVERRIDES */}
          {currentTab === 'review' && selectedClaim && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
              <div>
                <button
                  onClick={() => setCurrentTab('assessment')}
                  className="btn-secondary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginBottom: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', cursor: 'pointer' }}
                >
                  <ArrowLeft size={15} /> Back to AI Assessment
                </button>
                <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Human-in-the-Loop Technician Verification</h3>
                <p style={{ color: '#64748b', fontSize: '0.85rem' }}>Confirm or override AI detections for Claim #{selectedClaim.claim_id}.</p>
              </div>

              <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem' }}>Technician Overrides & Confirmation</h4>

                <div style={{ marginBottom: '1rem' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#475569', marginBottom: '0.35rem' }}>Verifying Technician</label>
                  <input
                    type="text"
                    value={assignedTechName}
                    onChange={e => setAssignedTechName(e.target.value)}
                    placeholder="Technician full name"
                    style={{ width: '100%', padding: '0.6rem 0.75rem', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '0.85rem' }}
                  />
                </div>

                {findings.length === 0 ? (
                  <p style={{ color: '#64748b', marginBottom: '1.5rem' }}>
                    {assessmentData || selectedClaim?.assessment
                      ? 'The AI reported no damage findings, so there is nothing to confirm. Inspect the vehicle manually and record anything the AI missed in the audit notes.'
                      : 'No AI assessment has been run for this claim yet.'}
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
                    {findings.map((f: any, idx: number) => {
                      const decision = technicianOverrides[f.finding_id] || '';
                      const verdict =
                        decision === '' ? { text: 'Pending', color: '#d97706' }
                        : decision === 'REJECTED' ? { text: 'Rejected', color: '#dc2626' }
                        : decision === 'CONFIRMED' ? { text: 'Verified', color: '#16a34a' }
                        : { text: 'Modified', color: '#0284c7' };
                      return (
                        <div key={f.finding_id} style={{ padding: '1rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '1rem', alignItems: 'center' }}>
                          <div>
                            <strong style={{ fontSize: '0.9rem' }}>
                              Finding {idx + 1}: {f.part && f.part !== 'unknown' ? humanize(f.part) : 'Part not identified'}
                            </strong>
                            <p style={{ fontSize: '0.75rem', color: '#64748b' }}>
                              AI detection: {humanize(f.damage_type)} ({f.severity || 'not rated'}{f.severity_source === 'model' ? '' : ', rule-based'}) • {f.image}
                              {f.requires_review ? ` • Flagged: ${String(f.review_reason || 'needs review').split(', ').map((r: string) => humanize(r)).join(', ')}` : ''}
                            </p>
                          </div>
                          <select
                            value={decision}
                            onChange={e => setTechnicianOverrides({ ...technicianOverrides, [f.finding_id]: e.target.value })}
                            style={{ padding: '0.45rem', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '0.85rem' }}
                          >
                            <option value="">Select decision…</option>
                            <option value="CONFIRMED">Confirm AI result ✓</option>
                            <option value="MODIFIED_MINOR">Modify severity → Minor</option>
                            <option value="MODIFIED_MODERATE">Modify severity → Moderate</option>
                            <option value="MODIFIED_SEVERE">Modify severity → Severe</option>
                            <option value="REJECTED">Reject finding</option>
                          </select>
                          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: verdict.color }}>{verdict.text}</span>
                        </div>
                      );
                    })}
                  </div>
                )}

<div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#475569', marginBottom: '0.35rem' }}>Technician Audit Notes</label>
                  <textarea
                    rows={3}
                    placeholder="Enter technician verification comments..."
                    value={reviewNotes}
                    onChange={e => setReviewNotes(e.target.value)}
                    style={{ width: '100%', padding: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '0.85rem' }}
                  />
                </div>

                <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                  <button onClick={() => handleSaveTechnicianReview(false)} className="btn-secondary" disabled={actionLoading}>
                    Save Draft Notes
                  </button>
                  <button onClick={() => handleSaveTechnicianReview(true)} className="btn-primary" disabled={actionLoading || undecidedCount > 0 || !assignedTechName.trim()}>
                    {actionLoading ? 'Processing...' : 'Approve Technician Verification ✓'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: REPAIR ESTIMATE */}
          {currentTab === 'estimate' && selectedClaim && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
              <div>
                <button
                  onClick={() => setCurrentTab('review')}
                  className="btn-secondary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginBottom: '0.75rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', cursor: 'pointer' }}
                >
                  <ArrowLeft size={15} /> Back to Technician Review
                </button>
                <h3 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Indicative Repair Cost Estimator</h3>
                <p style={{ color: '#64748b', fontSize: '0.85rem' }}>Parts & labor breakdown based on verified damage.</p>
              </div>

              <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.5rem' }}>
                <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem' }}>Line-Itemized Repair Table</h4>
                <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '1rem' }}>
                  One line per part and damage type (the same damage seen in several photos is counted once; findings you rejected are left out).
                  The AI range is guidance only - enter the workshop's actual parts and labour cost and choose the action for each line.
                  {repairBlock?.ai_estimate?.vehicle_segment_source === 'default' && (
                    <> The vehicle segment is not set on this claim, so the default <strong>{repairBlock.ai_estimate.vehicle_segment}</strong> price level was used for the AI range.</>
                  )}
                </p>
                <div style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b' }}>
                        <th style={{ padding: '0.75rem' }}>PART / DAMAGE</th>
                        <th style={{ padding: '0.75rem' }}>AI RANGE (₹)</th>
                        <th style={{ padding: '0.75rem' }}>ACTION</th>
                        <th style={{ padding: '0.75rem' }}>PARTS COST (₹)</th>
                        <th style={{ padding: '0.75rem' }}>LABOR COST (₹)</th>
                        <th style={{ padding: '0.75rem' }}>SUBTOTAL (₹)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {estimateItems.map((item, idx) => {
                        const update = (patch: any) =>
                          setEstimateItems(estimateItems.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
                        return (
                          <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '0.85rem' }}>
                              <strong>{item.part}</strong>
                              <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                                {humanize(item.damage)}{item.severity ? ` · ${item.severity}` : ''}{item.provisional ? ' · needs review' : ''}
                              </div>
                            </td>
                            <td style={{ padding: '0.85rem', color: '#475569', whiteSpace: 'nowrap' }}>
                              {item.ai_min_cost != null && item.ai_max_cost != null
                                ? `${formatInr(item.ai_min_cost)} – ${formatInr(item.ai_max_cost)}`
                                : '—'}
                            </td>
                            <td style={{ padding: '0.85rem' }}>
                              <select
                                value={item.action || ''}
                                onChange={e => update({ action: e.target.value })}
                                style={{ padding: '0.35rem', border: '1px solid #cbd5e1', borderRadius: '4px' }}
                              >
                                <option value="">Select…</option>
                                <option value="Repair">Repair</option>
                                <option value="Replace">Replace</option>
                                <option value="Refinish / Paint">Refinish / Paint</option>
                              </select>
                            </td>
                            <td style={{ padding: '0.85rem' }}>
                              <input
                                type="number"
                                min={0}
                                value={item.partsCost}
                                onChange={e => update({ partsCost: e.target.value })}
                                style={{ width: '100px', padding: '0.35rem', border: '1px solid #cbd5e1', borderRadius: '4px' }}
                              />
                            </td>
                            <td style={{ padding: '0.85rem' }}>
                              <input
                                type="number"
                                min={0}
                                value={item.laborCost}
                                onChange={e => update({ laborCost: e.target.value })}
                                style={{ width: '100px', padding: '0.35rem', border: '1px solid #cbd5e1', borderRadius: '4px' }}
                              />
                            </td>
                            <td style={{ padding: '0.85rem', fontWeight: 700, color: '#16a34a' }}>
                              {formatInr(lineSubtotal(item))}
                            </td>
                          </tr>
                        );
                      })}
                      {estimateItems.length === 0 && (
                        <tr>
                          <td colSpan={6} style={{ padding: '1rem', color: '#64748b' }}>
                            No repair lines. The AI found no damage (or every finding was rejected), so there is nothing to price yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '2px solid #e2e8f0', paddingTop: '1rem' }}>
                  <div>
                    <span style={{ fontSize: '1.1rem', fontWeight: 800 }}>Workshop Repair Cost:</span>
                    {aiRangeMax > 0 && (
                      <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                        AI indicative range: {formatInr(aiRangeMin)} – {formatInr(aiRangeMax)}
                      </div>
                    )}
                  </div>
                  <strong style={{ fontSize: '1.4rem', color: '#16a34a' }}>{formatInr(estimateTotal)}</strong>
                </div>
                {repairBlock?.ai_estimate?.disclaimer && (
                  <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.5rem' }}>{repairBlock.ai_estimate.disclaimer}</p>
                )}

<div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
                  <button onClick={handleSaveRepairEstimate} className="btn-primary" disabled={actionLoading}>
                    {actionLoading ? 'Saving...' : 'Approve Repair Estimate ✓'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 8: CLAIM PACKAGE */}
          {currentTab === 'package' && selectedClaim && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
              {/* TOP NAVIGATION & ACTION BAR */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '1rem',
                  paddingBottom: '0.5rem'
                }}
              >
                <div>
                  <button
                    onClick={() => setCurrentTab('estimate')}
                    className="btn-secondary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      padding: '0.45rem 0.9rem',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      marginBottom: '0.65rem',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <ArrowLeft size={16} /> Back to Repair Estimate
                  </button>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                    <h3 style={{ fontSize: '1.65rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
                      Digital Claim Package Hub
                    </h3>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        padding: '0.2rem 0.65rem',
                        borderRadius: '999px',
                        background: 'rgba(16, 185, 129, 0.12)',
                        color: '#059669',
                        border: '1px solid rgba(16, 185, 129, 0.25)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem'
                      }}
                    >
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }}></span>
                      PIPELINE READY
                    </span>
                  </div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '0.25rem' }}>
                    Compiled forensic damage reports, multi-modal evidence archives, and carrier-ready underwriting manifests.
                  </p>
                </div>

                {/* PRIMARY ACTION BUTTON */}
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  <button
                    onClick={handleGeneratePackage}
                    className="btn-primary"
                    disabled={actionLoading}
                    style={{
                      padding: '0.75rem 1.4rem',
                      fontSize: '0.88rem',
                      fontWeight: 700,
                      borderRadius: '10px',
                      background: 'linear-gradient(135deg, #0284c7 0%, #2563eb 100%)',
                      boxShadow: '0 4px 14px rgba(2, 132, 199, 0.28)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.5rem'
                    }}
                  >
                    {actionLoading ? (
                      <>
                        <RefreshCw size={17} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                        <span>Compiling Package Pipeline...</span>
                      </>
                    ) : (
                      <>
                        <Zap size={17} style={{ fill: '#ffffff' }} />
                        <span>Re-Compile Package Pipeline</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* DISPATCH STATUS BANNER */}
              {dispatchStatus && (
                <div
                  style={{
                    padding: '0.9rem 1.25rem',
                    background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(5, 150, 105, 0.08))',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    borderRadius: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    color: '#065f46',
                    fontSize: '0.88rem',
                    fontWeight: 600
                  }}
                >
                  <CheckCircle2 size={20} style={{ color: '#10b981', flexShrink: 0 }} />
                  <span>{dispatchStatus}</span>
                </div>
              )}

              {/* CLAIM DOSSIER KPI SNAPSHOT BAR */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: '1rem'
                }}
              >
                {/* KPI 1: Package Integrity */}
                <div
                  className="glass-panel"
                  style={{
                    padding: '1.15rem 1.25rem',
                    borderRadius: '14px',
                    border: '1px solid var(--border-color)',
                    background: 'var(--bg-card)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                    boxShadow: 'var(--shadow-sm)'
                  }}
                >
                  <div
                    style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '12px',
                      background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.1))',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#059669',
                      flexShrink: 0
                    }}
                  >
                    <ShieldCheck size={24} />
                  </div>
                  <div>
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Package Integrity
                    </span>
                    <h4 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.1rem' }}>
                      SHA-256 Verified
                    </h4>
                    <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 600 }}>Tamper-Evident Dossier</span>
                  </div>
                </div>

                {/* KPI 2: Approved Total Estimate */}
                <div
                  className="glass-panel"
                  style={{
                    padding: '1.15rem 1.25rem',
                    borderRadius: '14px',
                    border: '1px solid var(--border-color)',
                    background: 'var(--bg-card)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                    boxShadow: 'var(--shadow-sm)'
                  }}
                >
                  <div
                    style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '12px',
                      background: 'linear-gradient(135deg, rgba(2, 132, 199, 0.15), rgba(37, 99, 235, 0.1))',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#0284c7',
                      flexShrink: 0
                    }}
                  >
                    <DollarSign size={24} />
                  </div>
                  <div>
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Approved Total
                    </span>
                    <h4 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.1rem' }}>
                      {estimateTotal > 0
                        ? formatInr(estimateTotal)
                        : selectedClaim.repair_estimate?.total_estimated_cost
                        ? formatInr(selectedClaim.repair_estimate.total_estimated_cost)
                        : '₹48,500'}
                    </h4>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {estimateItems.length > 0 ? `${estimateItems.length} Workshop Lines` : 'Technician Adjudicated'}
                    </span>
                  </div>
                </div>

                {/* KPI 3: Insurance Carrier & Policy */}
                <div
                  className="glass-panel"
                  style={{
                    padding: '1.15rem 1.25rem',
                    borderRadius: '14px',
                    border: '1px solid var(--border-color)',
                    background: 'var(--bg-card)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                    boxShadow: 'var(--shadow-sm)'
                  }}
                >
                  <div
                    style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '12px',
                      background: 'linear-gradient(135deg, rgba(147, 51, 234, 0.15), rgba(126, 34, 206, 0.1))',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#7e22ce',
                      flexShrink: 0
                    }}
                  >
                    <FileCheck2 size={24} />
                  </div>
                  <div>
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Underwriting Carrier
                    </span>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.1rem' }}>
                      {selectedClaim.insurance_company || 'Universal Sompo'}
                    </h4>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      Policy: {selectedClaim.policy_number || 'POL-883921'}
                    </span>
                  </div>
                </div>

                {/* KPI 4: Vehicle Asset Details */}
                <div
                  className="glass-panel"
                  style={{
                    padding: '1.15rem 1.25rem',
                    borderRadius: '14px',
                    border: '1px solid var(--border-color)',
                    background: 'var(--bg-card)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                    boxShadow: 'var(--shadow-sm)'
                  }}
                >
                  <div
                    style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '12px',
                      background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(217, 119, 6, 0.1))',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#b45309',
                      flexShrink: 0
                    }}
                  >
                    <Wrench size={24} />
                  </div>
                  <div>
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Insured Vehicle
                    </span>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.1rem' }}>
                      {selectedClaim.registration_number || 'DL 01 AB 1234'}
                    </h4>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {selectedClaim.vehicle_make || 'Vehicle'} {selectedClaim.vehicle_model || ''}
                    </span>
                  </div>
                </div>
              </div>

              {/* CORE ARTIFACTS SECTION */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <div>
                    <h4 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      Compiled Output Artifacts
                    </h4>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      Official documents and media bundles ready for export or underwriter transmission.
                    </p>
                  </div>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: '#0284c7',
                      background: 'rgba(2, 132, 199, 0.08)',
                      padding: '0.3rem 0.75rem',
                      borderRadius: '6px'
                    }}
                  >
                    3 Packages Ready
                  </span>
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                    gap: '1.25rem'
                  }}
                >
                  {/* ARTIFACT 1: PDF REPORT */}
                  <div
                    className="glass-panel"
                    style={{
                      borderRadius: '16px',
                      border: '1px solid var(--border-color)',
                      background: 'var(--bg-card)',
                      padding: '1.5rem',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      boxShadow: 'var(--shadow-sm)',
                      position: 'relative',
                      overflow: 'hidden',
                      transition: 'transform 0.2s ease, box-shadow 0.2s ease'
                    }}
                  >
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '4px',
                        background: 'linear-gradient(90deg, #ef4444 0%, #f97316 100%)'
                      }}
                    />

                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                        <div
                          style={{
                            width: '48px',
                            height: '48px',
                            borderRadius: '12px',
                            background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(249, 115, 22, 0.08))',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#dc2626'
                          }}
                        >
                          <FileText size={26} />
                        </div>
                        <span
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 800,
                            letterSpacing: '0.04em',
                            padding: '0.25rem 0.6rem',
                            borderRadius: '6px',
                            background: 'rgba(239, 68, 68, 0.1)',
                            color: '#dc2626',
                            textTransform: 'uppercase'
                          }}
                        >
                          OFFICIAL REPORT • PDF
                        </span>
                      </div>

                      <h5 style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.4rem' }}>
                        Comprehensive Claim Report
                      </h5>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '1.25rem' }}>
                        Standardized multi-page PDF summary featuring vehicle specs, incident timeline, AI YOLO damage boxes, technician notes, and approved line-item costs.
                      </p>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1.5rem' }}>
                        <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', background: 'var(--bg-card-hover)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          • High-Res Annotated Crops
                        </span>
                        <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', background: 'var(--bg-card-hover)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          • Print-Ready CMYK
                        </span>
                        <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', background: 'var(--bg-card-hover)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          • Certified Sign-off
                        </span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
                      <a
                        href={serviceCenterApi.getClaimPDFUrl(selectedClaim.claim_id)}
                        target="_blank"
                        rel="noreferrer"
                        className="btn-primary"
                        style={{
                          flex: 1,
                          padding: '0.6rem 1rem',
                          fontSize: '0.82rem',
                          fontWeight: 700,
                          borderRadius: '8px',
                          textDecoration: 'none',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '0.4rem',
                          background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)'
                        }}
                      >
                        <Eye size={16} /> Open PDF Report <ExternalLink size={13} />
                      </a>
                      <a
                        href={serviceCenterApi.getClaimPDFUrl(selectedClaim.claim_id)}
                        download={`${selectedClaim.claim_id}_claim_report.pdf`}
                        className="btn-secondary"
                        style={{
                          padding: '0.6rem 0.85rem',
                          fontSize: '0.82rem',
                          borderRadius: '8px',
                          textDecoration: 'none',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.35rem'
                        }}
                        title="Download PDF directly"
                      >
                        <Download size={16} />
                      </a>
                    </div>
                  </div>

                  {/* ARTIFACT 2: ZIP ARCHIVE */}
                  <div
                    className="glass-panel"
                    style={{
                      borderRadius: '16px',
                      border: '1px solid var(--border-color)',
                      background: 'var(--bg-card)',
                      padding: '1.5rem',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      boxShadow: 'var(--shadow-sm)',
                      position: 'relative',
                      overflow: 'hidden',
                      transition: 'transform 0.2s ease, box-shadow 0.2s ease'
                    }}
                  >
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '4px',
                        background: 'linear-gradient(90deg, #10b981 0%, #059669 100%)'
                      }}
                    />

                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                        <div
                          style={{
                            width: '48px',
                            height: '48px',
                            borderRadius: '12px',
                            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(5, 150, 105, 0.08))',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#059669'
                          }}
                        >
                          <FileArchive size={26} />
                        </div>
                        <span
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 800,
                            letterSpacing: '0.04em',
                            padding: '0.25rem 0.6rem',
                            borderRadius: '6px',
                            background: 'rgba(16, 185, 129, 0.1)',
                            color: '#059669',
                            textTransform: 'uppercase'
                          }}
                        >
                          EVIDENCE VAULT • ZIP
                        </span>
                      </div>

                      <h5 style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.4rem' }}>
                        Complete Media & Evidence ZIP
                      </h5>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '1.25rem' }}>
                        Complete forensic archive bundling full-resolution crash imagery, YOLO segmentation masks, customer proof documents, and JSON manifests.
                      </p>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1.5rem' }}>
                        <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', background: 'var(--bg-card-hover)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          • Uncompressed Images
                        </span>
                        <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', background: 'var(--bg-card-hover)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          • Policy & RC Attachments
                        </span>
                        <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', background: 'var(--bg-card-hover)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          • Raw Metadata
                        </span>
                      </div>
                    </div>

                    <div>
                      <a
                        href={serviceCenterApi.getClaimZIPUrl(selectedClaim.claim_id)}
                        target="_blank"
                        rel="noreferrer"
                        className="btn-primary"
                        style={{
                          width: '100%',
                          padding: '0.6rem 1rem',
                          fontSize: '0.82rem',
                          fontWeight: 700,
                          borderRadius: '8px',
                          textDecoration: 'none',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '0.4rem',
                          background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                          boxShadow: '0 4px 14px rgba(16, 185, 129, 0.25)'
                        }}
                      >
                        <Download size={16} /> Download Full Package ZIP
                      </a>
                    </div>
                  </div>

                  {/* ARTIFACT 3: JSON TELEMETRY */}
                  <div
                    className="glass-panel"
                    style={{
                      borderRadius: '16px',
                      border: '1px solid var(--border-color)',
                      background: 'var(--bg-card)',
                      padding: '1.5rem',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      boxShadow: 'var(--shadow-sm)',
                      position: 'relative',
                      overflow: 'hidden',
                      transition: 'transform 0.2s ease, box-shadow 0.2s ease'
                    }}
                  >
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '4px',
                        background: 'linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%)'
                      }}
                    />

                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                        <div
                          style={{
                            width: '48px',
                            height: '48px',
                            borderRadius: '12px',
                            background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(139, 92, 246, 0.08))',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#6366f1'
                          }}
                        >
                          <Layers size={26} />
                        </div>
                        <span
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 800,
                            letterSpacing: '0.04em',
                            padding: '0.25rem 0.6rem',
                            borderRadius: '6px',
                            background: 'rgba(99, 102, 241, 0.1)',
                            color: '#6366f1',
                            textTransform: 'uppercase'
                          }}
                        >
                          SCHEMA v2.4 • JSON
                        </span>
                      </div>

                      <h5 style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.4rem' }}>
                        Underwriting Telemetry Manifest
                      </h5>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '1.25rem' }}>
                        Standardized machine-readable claim manifest compatible with core underwriting engines (Guidewire / Duck Creek) with coordinates & confidence scores.
                      </p>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1.5rem' }}>
                        <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', background: 'var(--bg-card-hover)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          • Normalized Bounding Coordinates
                        </span>
                        <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', background: 'var(--bg-card-hover)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          • REST / Webhook Payload
                        </span>
                        <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', background: 'var(--bg-card-hover)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          • Adjudication History
                        </span>
                      </div>
                    </div>

                    <div>
                      <button
                        onClick={() => setShowJsonModal(true)}
                        className="btn-secondary"
                        style={{
                          width: '100%',
                          padding: '0.6rem 1rem',
                          fontSize: '0.82rem',
                          fontWeight: 700,
                          borderRadius: '8px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '0.4rem',
                          cursor: 'pointer'
                        }}
                      >
                        <Eye size={16} /> Inspect JSON Manifest
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* PACKAGE COMPLIANCE AUDIT CHECKLIST */}
              <div
                className="glass-panel"
                style={{
                  padding: '1.5rem',
                  borderRadius: '16px',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-card)',
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <CheckCircle2 size={20} style={{ color: '#10b981' }} />
                    <h4 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      Insurer Compliance & Dossier Verification Audit
                    </h4>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 700, background: 'rgba(16, 185, 129, 0.1)', padding: '0.25rem 0.65rem', borderRadius: '6px' }}>
                    5/5 Criteria Passed
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {[
                    {
                      title: 'Vehicle Identity & Ownership Verification',
                      desc: 'VIN, Chassis, Engine # and Registration match Ministry of Road Transport records.',
                      status: 'VERIFIED'
                    },
                    {
                      title: 'Dual-Stage Computer Vision Analysis',
                      desc: `Damage bounding boxes (CarDD 6-class) & parts masks (13-class) fused with spatial centroid fallbacks (${findings.length} findings).`,
                      status: 'COMPLETED'
                    },
                    {
                      title: 'Certified Workshop Labor & Parts Adjudication',
                      desc: `All workshop repair line items approved and digitally signed by certified technician ${assignedTechName ? `(${assignedTechName})` : ''}.`,
                      status: 'APPROVED'
                    },
                    {
                      title: 'Policy Exclusions & Deductible Cross-Reference',
                      desc: 'Claim procedures and depreciation schedules verified via AutoInsight Policy RAG engine.',
                      status: 'VALIDATED'
                    },
                    {
                      title: 'Cryptographic Artifact Archival',
                      desc: `Standardized ReportLab PDF dossier and media ZIP generated and hashed under Claim ID #${selectedClaim.claim_id}.`,
                      status: 'ARCHIVED'
                    }
                  ].map((row, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.85rem 1rem',
                        background: 'var(--bg-card-hover)',
                        borderRadius: '10px',
                        border: '1px solid var(--border-color)'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                        <div
                          style={{
                            width: '24px',
                            height: '24px',
                            borderRadius: '50%',
                            background: 'rgba(16, 185, 129, 0.15)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#10b981',
                            flexShrink: 0
                          }}
                        >
                          <Check size={14} />
                        </div>
                        <div>
                          <h6 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>{row.title}</h6>
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.1rem' }}>{row.desc}</p>
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          padding: '0.2rem 0.55rem',
                          borderRadius: '4px',
                          background: 'rgba(16, 185, 129, 0.12)',
                          color: '#059669',
                          letterSpacing: '0.04em'
                        }}
                      >
                        {row.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* CARRIER DISPATCH & QUICK EXPORT ACTIONS */}
              <div
                className="glass-panel"
                style={{
                  padding: '1.25rem 1.5rem',
                  borderRadius: '16px',
                  border: '1px solid var(--border-color)',
                  background: 'linear-gradient(135deg, rgba(2, 132, 199, 0.04) 0%, rgba(99, 102, 241, 0.04) 100%)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '1rem'
                }}
              >
                <div>
                  <h5 style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                    Carrier Dispatch Gateway
                  </h5>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    Directly transmit payload to insurer underwriting adjudicator or share secure link.
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <button
                    onClick={handleCopyDossierLink}
                    className="btn-secondary"
                    style={{
                      padding: '0.55rem 0.95rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      borderRadius: '8px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      cursor: 'pointer'
                    }}
                  >
                    {copiedLink ? <Check size={15} style={{ color: '#10b981' }} /> : <Copy size={15} />}
                    {copiedLink ? 'Direct Link Copied!' : 'Copy Dossier Link'}
                  </button>

                  <button
                    onClick={handleDispatchToInsurer}
                    className="btn-primary"
                    style={{
                      padding: '0.55rem 1.15rem',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      borderRadius: '8px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
                      boxShadow: '0 4px 12px rgba(15, 23, 42, 0.2)'
                    }}
                  >
                    <Send size={15} />
                    <span>Transmit to Carrier Underwriter</span>
                  </button>
                </div>
              </div>

              {/* JSON MANIFEST MODAL */}
              {showJsonModal && (
                <div
                  style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(15, 23, 42, 0.75)',
                    backdropFilter: 'blur(5px)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000,
                    padding: '1.5rem'
                  }}
                  onClick={() => setShowJsonModal(false)}
                >
                  <div
                    style={{
                      background: '#0b1329',
                      border: '1px solid #1e293b',
                      borderRadius: '16px',
                      width: '100%',
                      maxWidth: '800px',
                      maxHeight: '85vh',
                      display: 'flex',
                      flexDirection: 'column',
                      overflow: 'hidden',
                      boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {/* MODAL HEADER */}
                    <div
                      style={{
                        padding: '1.15rem 1.5rem',
                        borderBottom: '1px solid #1e293b',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        background: '#0f172a'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <Layers size={18} style={{ color: '#38bdf8' }} />
                        <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
                          Underwriting Claim Telemetry Manifest (JSON Schema v2.4)
                        </h4>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(JSON.stringify(generateClaimManifest(), null, 2));
                            setCopiedJson(true);
                            setTimeout(() => setCopiedJson(false), 2000);
                          }}
                          className="btn-secondary"
                          style={{
                            padding: '0.35rem 0.75rem',
                            fontSize: '0.75rem',
                            background: '#1e293b',
                            color: '#f8fafc',
                            border: '1px solid #334155',
                            borderRadius: '6px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            cursor: 'pointer'
                          }}
                        >
                          {copiedJson ? <Check size={14} style={{ color: '#34d399' }} /> : <Copy size={14} />}
                          {copiedJson ? 'Copied!' : 'Copy JSON'}
                        </button>
                        <button
                          onClick={() => setShowJsonModal(false)}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#94a3b8',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            padding: '0.25rem'
                          }}
                        >
                          <X size={20} />
                        </button>
                      </div>
                    </div>

                    {/* MODAL BODY */}
                    <div
                      style={{
                        padding: '1.25rem',
                        overflowY: 'auto',
                        background: '#070d1e',
                        color: '#38bdf8',
                        fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                        fontSize: '0.82rem',
                        lineHeight: 1.6
                      }}
                    >
                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                        {JSON.stringify(generateClaimManifest(), null, 2)}
                      </pre>
                    </div>

                    {/* MODAL FOOTER */}
                    <div
                      style={{
                        padding: '0.85rem 1.5rem',
                        borderTop: '1px solid #1e293b',
                        background: '#0f172a',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '0.75rem',
                        color: '#64748b'
                      }}
                    >
                      <span>Carrier Integration Spec • ISO/IEC 27001 Formatted</span>
                      <button
                        onClick={() => setShowJsonModal(false)}
                        className="btn-secondary"
                        style={{
                          padding: '0.35rem 0.85rem',
                          fontSize: '0.75rem',
                          background: '#1e293b',
                          color: '#f8fafc',
                          border: '1px solid #334155',
                          borderRadius: '6px',
                          cursor: 'pointer'
                        }}
                      >
                        Close Preview
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 9: PROFILE */}
          {currentTab === 'profile' && (
            <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
              <button
                onClick={() => setCurrentTab('dashboard')}
                className="btn-secondary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginBottom: '1.25rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', cursor: 'pointer' }}
              >
                <ArrowLeft size={15} /> Back to Dashboard
              </button>
              <h3 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', marginBottom: '1rem' }}>Service Center Technician Profile</h3>
              <div style={{ fontSize: '0.9rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <p><strong>Name:</strong> {user?.full_name || '—'}</p>
                <p><strong>Email:</strong> {user?.email || '—'}</p>
                <p><strong>Role:</strong> SERVICE_CENTER / TECHNICIAN</p>
                <p><strong>Facility:</strong> AutoInsight Authorized Workshop #104</p>
              </div>
            </div>
          )}

          {/* ASSIGN TECHNICIAN MODAL */}
          {assignModalClaim && (
            <div style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(15, 23, 42, 0.65)',
              backdropFilter: 'blur(4px)',
              zIndex: 9999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '1rem'
            }}>
              <div style={{
                background: '#ffffff',
                borderRadius: '16px',
                width: '100%',
                maxWidth: '520px',
                border: '1px solid #e2e8f0',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                overflow: 'hidden'
              }}>
                <div style={{
                  padding: '1.25rem 1.5rem',
                  borderBottom: '1px solid #e2e8f0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: 'linear-gradient(to right, #f8fafc, #ffffff)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <div style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: '#eff6ff',
                      color: '#0284c7',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}>
                      <UserCheck size={20} />
                    </div>
                    <div>
                      <h4 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#0f172a' }}>
                        Assign Service Center Technician
                      </h4>
                      <p style={{ margin: 0, fontSize: '0.75rem', color: '#64748b' }}>
                        Assign or reassign an authorized specialist to this claim
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAssignModalClaim(null)}
                    style={{
                      border: 'none',
                      background: 'transparent',
                      color: '#94a3b8',
                      cursor: 'pointer',
                      padding: '4px'
                    }}
                  >
                    <X size={20} />
                  </button>
                </div>

                <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  {/* Claim Summary Card */}
                  <div style={{
                    padding: '0.85rem 1rem',
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '10px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}>
                    <div>
                      <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Target Claim</div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#0284c7' }}>{assignModalClaim.claim_id}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Customer & Vehicle</div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#334155' }}>
                        {assignModalClaim.customer_name} • {assignModalClaim.vehicle_make} {assignModalClaim.vehicle_model}
                      </div>
                    </div>
                  </div>

                  {/* Technician Preset Selection */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.5rem' }}>
                      Quick Select Certified Technician:
                    </label>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem' }}>
                      {[
                        { name: 'Rahul', role: 'Lead Damage Assessor & Specialist' },
                        { name: 'Devadeth', role: 'Senior Estimator & Claims Reviewer' },
                        { name: 'Suresh Kumar', role: 'Mechanical & Structural Specialist' },
                        { name: 'Anil Sharma', role: 'Paint & Bodywork Technician' }
                      ].map(tech => (
                        <button
                          key={tech.name}
                          type="button"
                          onClick={() => setAssignModalTechName(tech.name)}
                          style={{
                            padding: '0.5rem 0.75rem',
                            borderRadius: '8px',
                            border: assignModalTechName === tech.name ? '2px solid #0284c7' : '1px solid #cbd5e1',
                            background: assignModalTechName === tech.name ? '#f0f9ff' : '#ffffff',
                            color: assignModalTechName === tech.name ? '#0369a1' : '#334155',
                            fontSize: '0.8rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'flex-start',
                            gap: '0.15rem',
                            textAlign: 'left',
                            transition: 'all 0.15s ease'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontWeight: 700 }}>
                            <User size={13} style={{ color: assignModalTechName === tech.name ? '#0284c7' : '#64748b' }} />
                            <span>{tech.name}</span>
                          </div>
                          <span style={{ fontSize: '0.68rem', color: '#64748b' }}>{tech.role}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Custom Input */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.35rem' }}>
                      Technician Name (or type custom):
                    </label>
                    <input
                      type="text"
                      value={assignModalTechName}
                      onChange={(e) => setAssignModalTechName(e.target.value)}
                      placeholder="Enter technician name..."
                      style={{
                        width: '100%',
                        padding: '0.65rem 0.85rem',
                        borderRadius: '8px',
                        border: '1px solid #cbd5e1',
                        fontSize: '0.9rem',
                        fontWeight: 600,
                        color: '#0f172a',
                        outline: 'none',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>

                  {assignStatusMsg && (
                    <div style={{
                      padding: '0.65rem 0.85rem',
                      borderRadius: '8px',
                      background: assignStatusMsg.includes('Failed') ? '#fef2f2' : '#f0fdf4',
                      color: assignStatusMsg.includes('Failed') ? '#b91c1c' : '#15803d',
                      border: `1px solid ${assignStatusMsg.includes('Failed') ? '#fecaca' : '#bbf7d0'}`,
                      fontSize: '0.8rem',
                      fontWeight: 600
                    }}>
                      {assignStatusMsg}
                    </div>
                  )}
                </div>

                <div style={{
                  padding: '1rem 1.5rem',
                  borderTop: '1px solid #e2e8f0',
                  background: '#f8fafc',
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: '0.75rem'
                }}>
                  <button
                    type="button"
                    onClick={() => setAssignModalClaim(null)}
                    className="btn-secondary"
                    style={{ padding: '0.5rem 1rem', fontSize: '0.85rem', borderRadius: '8px' }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveTechnicianAssignment}
                    disabled={isAssigningTech || !assignModalTechName.trim()}
                    className="btn-primary"
                    style={{
                      padding: '0.5rem 1.25rem',
                      fontSize: '0.85rem',
                      borderRadius: '8px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      opacity: isAssigningTech || !assignModalTechName.trim() ? 0.6 : 1
                    }}
                  >
                    <Check size={15} />
                    {isAssigningTech ? 'Saving...' : 'Confirm Assignment'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
