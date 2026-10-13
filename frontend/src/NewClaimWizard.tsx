import React, { useState } from 'react';
import { api, type Vehicle, type Claim, type User } from './api';
import { ArrowLeft, ArrowRight, CheckCircle2, Car, FileText, UploadCloud, AlertCircle } from 'lucide-react';

interface NewClaimWizardProps {
  vehicles: Vehicle[];
  user: User;
  onNavigate: (route: string) => void;
  onClaimSubmitted: (claim: Claim) => void;
}

export const NewClaimWizard: React.FC<NewClaimWizardProps> = ({
  vehicles,
  user,
  onNavigate,
  onClaimSubmitted
}) => {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [selectedVehicleId, setSelectedVehicleId] = useState<number>(vehicles[0]?.id || 0);
  const [customerAddress, setCustomerAddress] = useState(
    [user.address_line, user.city, user.state, user.pincode, user.country].filter(Boolean).join(', ')
  );

  // Step 2: Accident details (All mandatory except description)
  const [accidentDate, setAccidentDate] = useState('');
  const [accidentTime, setAccidentTime] = useState('');
  const [accidentLocation, setAccidentLocation] = useState('');
  const [accidentType, setAccidentType] = useState('');
  const [description, setDescription] = useState(''); // OPTIONAL

  // Step 3: Insurance information & Documents (All mandatory)
  const [insurerName, setInsurerName] = useState('');
  const [policyNo, setPolicyNo] = useState('');
  const [policyType, setPolicyType] = useState('');
  const [policyExpiry, setPolicyExpiry] = useState('');

  // Document files (RC, DL, Policy Document - Mandatory)
  const [rcFile, setRcFile] = useState<File | null>(null);
  const [dlFile, setDlFile] = useState<File | null>(null);
  const [policyDocFile, setPolicyDocFile] = useState<File | null>(null);

  // Validation Error messages
  const [step2Error, setStep2Error] = useState('');
  const [step3Error, setStep3Error] = useState('');

  const [loading, setLoading] = useState(false);
  const [createdClaim, setCreatedClaim] = useState<Claim | null>(null);

  const selectedVehicle = vehicles.find((v) => v.id === selectedVehicleId) || vehicles[0];

  const handleNextFromStep2 = () => {
    setStep2Error('');
    if (!accidentDate || !accidentTime || !accidentLocation || !accidentType) {
      setStep2Error('Please fill in all required accident fields (Date, Time, Location, Type). Only Description is optional.');
      return;
    }
    setStep(3);
  };

  const handleNextFromStep3 = () => {
    setStep3Error('');
    if (!insurerName || !policyNo || !policyType || !policyExpiry) {
      setStep3Error('Please fill in all policy details (Insurer Name, Policy Number, Policy Type, Expiry Date).');
      return;
    }
    if (!policyDocFile || !rcFile || !dlFile) {
      setStep3Error('Document upload is mandatory. Please attach Policy Document, Vehicle RC, and Driving Licence.');
      return;
    }
    setStep(4);
  };

  const handleSubmitClaim = async () => {
    setLoading(true);

    try {
      // 1. Submit Claim to FastAPI backend
      const claimRes = await api.post('/claims', {
        vehicle_id: selectedVehicleId,
        customer_address: customerAddress.trim() || null,
        accident_date: accidentDate,
        accident_time: accidentTime,
        accident_type: accidentType,
        accident_location: accidentLocation,
        accident_description: description.trim() || null,
        insurance_company: insurerName,
        policy_number: policyNo,
        policy_type: policyType,
        policy_expiry: policyExpiry
      });

      const claimId = claimRes.data.claim_id;

      // 2. Upload attached mandatory documents (Policy Doc, RC, Driving License)
      const docsToUpload = [
        { file: policyDocFile, name: 'Policy_Document' },
        { file: rcFile, name: 'Registration_Certificate_RC' },
        { file: dlFile, name: 'Driving_Licence' }
      ];
      const failedUploads: string[] = [];

      for (const doc of docsToUpload) {
        if (doc.file) {
          const formData = new FormData();
          formData.append('file', doc.file, `${doc.name}_${doc.file.name}`);
          try {
            await api.post(`/documents/claims/${claimId}/evidence`, formData, {
              headers: { 'Content-Type': 'multipart/form-data' }
            });
          } catch (e) {
            console.warn(`Failed to upload ${doc.name}`, e);
            failedUploads.push(doc.name);
          }
        }
      }

      // 3. Fetch fresh created claim record
      const listRes = await api.get('/claims');
      const updated = listRes.data.find((c: Claim) => c.claim_id === claimId) || claimRes.data;

      setCreatedClaim(updated);
      onClaimSubmitted(updated);
      setLoading(false);
      if (failedUploads.length) {
        alert(`Claim submitted, but these files could not be saved: ${failedUploads.join(', ')}. Open the claim details to upload them again.`);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit claim.');
      setLoading(false);
    }
  };

  if (createdClaim) {
    return (
      <div className="glass-panel" style={{ maxWidth: '650px', margin: '2rem auto', padding: '3rem', textAlign: 'center', background: '#ffffff' }}>
        <div style={{ width: '64px', height: '64px', background: '#dcfce7', color: '#15803d', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem auto' }}>
          <CheckCircle2 size={36} />
        </div>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a', marginBottom: '0.5rem' }}>
          Claim Submitted Successfully
        </h2>
        <p style={{ color: '#475569', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
          Claim ID: <strong>{createdClaim.claim_id}</strong>
        </p>
        <p style={{ fontSize: '0.9rem', color: '#64748b', background: '#f8fafc', padding: '1rem', borderRadius: 'var(--radius-md)', marginBottom: '2rem' }}>
          Your claim and mandatory policy documents (RC, Driving Licence, Policy Document) have been submitted to the backend database and sent to the <strong>Service Center Queue</strong>.
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
          <button onClick={() => onNavigate(`/claims/${createdClaim.claim_id}`)} className="btn-primary">
            Track Claim Status
          </button>
          <button onClick={() => onNavigate('/dashboard')} className="btn-secondary">
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '850px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* MULTI-STEP PROGRESS STEPPER */}
      <div className="glass-panel" style={{ padding: '1.25rem 2rem', background: '#ffffff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {[
          { num: 1, label: 'Vehicle *' },
          { num: 2, label: 'Accident Details *' },
          { num: 3, label: 'Policy & Documents *' },
          { num: 4, label: 'Review & Submit' }
        ].map((s) => (
          <div key={s.num} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <div
              style={{
                width: '30px',
                height: '30px',
                borderRadius: '50%',
                background: step === s.num ? '#0284c7' : step > s.num ? '#10b981' : '#f1f5f9',
                color: step === s.num || step > s.num ? 'white' : '#64748b',
                fontWeight: 700,
                fontSize: '0.8rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              {step > s.num ? <CheckCircle2 size={15} /> : s.num}
            </div>
            <span style={{ fontSize: '0.8rem', fontWeight: step === s.num ? 700 : 500, color: step === s.num ? '#0f172a' : '#94a3b8' }}>
              {s.label}
            </span>
          </div>
        ))}
      </div>

      {/* STEP 1: VEHICLE */}
      {step === 1 && (
        <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
          <h3 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.5rem' }}>Step 1 — Select Vehicle *</h3>
          <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '1.5rem' }}>Select the registered vehicle involved in the claim (Mandatory).</p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1.25rem', marginBottom: '2rem' }}>
            {vehicles.map((v) => (
              <div
                key={v.id}
                onClick={() => setSelectedVehicleId(v.id)}
                className="glass-panel glass-panel-hover"
                style={{
                  padding: '1.25rem',
                  cursor: 'pointer',
                  borderColor: selectedVehicleId === v.id ? '#0284c7' : 'var(--border-color)',
                  background: selectedVehicleId === v.id ? '#f0f9ff' : '#ffffff'
                }}
              >
                <Car size={24} style={{ color: '#0284c7', marginBottom: '0.5rem' }} />
                <h4 style={{ fontWeight: 700, color: '#0f172a' }}>{v.make} {v.model}</h4>
                <p style={{ fontSize: '0.85rem', color: '#64748b' }}>Reg #: {v.registration_number}</p>
                <p style={{ fontSize: '0.8rem', color: '#64748b' }}>VIN / Chassis #: {v.vin || 'Not provided'}</p>
                <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Engine #: {v.engine_number || 'Not provided'}</p>
                <span className="badge badge-success" style={{ marginTop: '0.5rem', fontSize: '0.65rem' }}>COVERED</span>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <button onClick={() => onNavigate('/vehicles/add')} className="btn-secondary">
              + Add New Vehicle
            </button>
            <button onClick={() => setStep(2)} className="btn-primary">
              Next: Accident Details <ArrowRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: ACCIDENT DETAILS */}
      {step === 2 && (
        <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
          <h3 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.5rem' }}>Step 2 — Accident Details</h3>
          <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
            All fields below are <strong>mandatory</strong>, except description which is optional.
          </p>

          {step2Error && (
            <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', background: '#fee2e2', border: '1px solid #fca5a5', color: '#b91c1c', fontSize: '0.85rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <AlertCircle size={18} /> {step2Error}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginBottom: '1.5rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#0f172a', marginBottom: '0.35rem', fontWeight: 700 }}>
                Accident Date <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input type="date" required value={accidentDate} onChange={(e) => setAccidentDate(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', outline: 'none' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#0f172a', marginBottom: '0.35rem', fontWeight: 700 }}>
                Approximate Time <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input type="time" required value={accidentTime} onChange={(e) => setAccidentTime(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', outline: 'none' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#0f172a', marginBottom: '0.35rem', fontWeight: 700 }}>
                Accident Location <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input required placeholder="Enter accident location..." value={accidentLocation} onChange={(e) => setAccidentLocation(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', outline: 'none' }} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#0f172a', marginBottom: '0.35rem', fontWeight: 700 }}>
                Accident Type <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <select required value={accidentType} onChange={(e) => setAccidentType(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', outline: 'none' }}>
                <option value="">Select Accident Type</option>
                <option value="Collision">Collision</option>
                <option value="Rear-end collision">Rear-end collision</option>
                <option value="Front collision">Front collision</option>
                <option value="Side collision">Side collision</option>
                <option value="Parking damage">Parking damage</option>
                <option value="Weather-related damage">Weather-related damage</option>
                <option value="Vandalism">Vandalism</option>
                <option value="Other">Other</option>
              </select>
            </div>

            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#475569', marginBottom: '0.35rem', fontWeight: 600 }}>
                Accident Description <span style={{ color: '#64748b', fontWeight: 400 }}>(Optional)</span>
              </label>
              <textarea rows={3} placeholder="Describe details of the incident (Optional)..." value={description} onChange={(e) => setDescription(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', outline: 'none' }} />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <button onClick={() => setStep(1)} className="btn-secondary"><ArrowLeft size={16} /> Back</button>
            <button onClick={handleNextFromStep2} className="btn-primary">Next: Policy & Documents <ArrowRight size={16} /></button>
          </div>
        </div>
      )}

      {/* STEP 3: POLICY & MANDATORY DOCUMENTS UPLOAD */}
      {step === 3 && (
        <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
          <h3 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.5rem' }}>Step 3 — Policy Details & Mandatory Documents Upload</h3>
          <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
            All policy fields and document uploads are <strong>mandatory</strong>.
          </p>

          {step3Error && (
            <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', background: '#fee2e2', border: '1px solid #fca5a5', color: '#b91c1c', fontSize: '0.85rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <AlertCircle size={18} /> {step3Error}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginBottom: '1.5rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#0f172a', marginBottom: '0.35rem', fontWeight: 700 }}>
                Insurer Name <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input required placeholder="e.g. State Auto Insurance" value={insurerName} onChange={(e) => setInsurerName(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#0f172a', marginBottom: '0.35rem', fontWeight: 700 }}>
                Policy Number <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input required placeholder="e.g. POL-123456" value={policyNo} onChange={(e) => setPolicyNo(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#0f172a', marginBottom: '0.35rem', fontWeight: 700 }}>
                Policy Type <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input required placeholder="e.g. Comprehensive" value={policyType} onChange={(e) => setPolicyType(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#0f172a', marginBottom: '0.35rem', fontWeight: 700 }}>
                Policy Expiry Date <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input required type="date" value={policyExpiry} onChange={(e) => setPolicyExpiry(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }} />
            </div>
          </div>

          <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a', marginTop: '1.5rem', marginBottom: '1rem' }}>
            Mandatory Documents Upload <span style={{ color: '#ef4444' }}>*</span>
          </h4>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
            {/* 1. Policy Document Upload */}
            <div style={{ border: policyDocFile ? '2px solid #10b981' : '2px dashed #cbd5e1', borderRadius: 'var(--radius-md)', padding: '1.25rem', textAlign: 'center', background: policyDocFile ? '#f0fdf4' : '#f8fafc' }}>
              <FileText size={28} style={{ color: policyDocFile ? '#10b981' : '#0284c7', marginBottom: '0.35rem' }} />
              <h5 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                Policy Document <span style={{ color: '#ef4444' }}>*</span>
              </h5>
              <p style={{ fontSize: '0.75rem', color: policyDocFile ? '#15803d' : '#64748b', marginBottom: '0.5rem', fontWeight: policyDocFile ? 600 : 400 }}>
                {policyDocFile ? policyDocFile.name : 'Upload Policy PDF/Image'}
              </p>
              <input
                type="file"
                accept=".pdf,image/*"
                onChange={(e) => e.target.files && setPolicyDocFile(e.target.files[0])}
                id="file-policy"
                style={{ display: 'none' }}
              />
              <label htmlFor="file-policy" className={policyDocFile ? "btn-secondary" : "btn-primary"} style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem', cursor: 'pointer' }}>
                {policyDocFile ? 'Change File' : 'Upload Policy *'}
              </label>
            </div>

            {/* 2. RC (Registration Certificate) Upload */}
            <div style={{ border: rcFile ? '2px solid #10b981' : '2px dashed #cbd5e1', borderRadius: 'var(--radius-md)', padding: '1.25rem', textAlign: 'center', background: rcFile ? '#f0fdf4' : '#f8fafc' }}>
              <UploadCloud size={28} style={{ color: rcFile ? '#10b981' : '#0284c7', marginBottom: '0.35rem' }} />
              <h5 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                Vehicle RC <span style={{ color: '#ef4444' }}>*</span>
              </h5>
              <p style={{ fontSize: '0.75rem', color: rcFile ? '#15803d' : '#64748b', marginBottom: '0.5rem', fontWeight: rcFile ? 600 : 400 }}>
                {rcFile ? rcFile.name : 'Upload Vehicle RC Document'}
              </p>
              <input
                type="file"
                accept=".pdf,image/*"
                onChange={(e) => e.target.files && setRcFile(e.target.files[0])}
                id="file-rc"
                style={{ display: 'none' }}
              />
              <label htmlFor="file-rc" className={rcFile ? "btn-secondary" : "btn-primary"} style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem', cursor: 'pointer' }}>
                {rcFile ? 'Change File' : 'Upload RC *'}
              </label>
            </div>

            {/* 3. Driving Licence Upload */}
            <div style={{ border: dlFile ? '2px solid #10b981' : '2px dashed #cbd5e1', borderRadius: 'var(--radius-md)', padding: '1.25rem', textAlign: 'center', background: dlFile ? '#f0fdf4' : '#f8fafc' }}>
              <UploadCloud size={28} style={{ color: dlFile ? '#10b981' : '#0284c7', marginBottom: '0.35rem' }} />
              <h5 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                Driving Licence (DL) <span style={{ color: '#ef4444' }}>*</span>
              </h5>
              <p style={{ fontSize: '0.75rem', color: dlFile ? '#15803d' : '#64748b', marginBottom: '0.5rem', fontWeight: dlFile ? 600 : 400 }}>
                {dlFile ? dlFile.name : 'Upload Driver DL Document'}
              </p>
              <input
                type="file"
                accept=".pdf,image/*"
                onChange={(e) => e.target.files && setDlFile(e.target.files[0])}
                id="file-dl"
                style={{ display: 'none' }}
              />
              <label htmlFor="file-dl" className={dlFile ? "btn-secondary" : "btn-primary"} style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem', cursor: 'pointer' }}>
                {dlFile ? 'Change File' : 'Upload DL *'}
              </label>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <button onClick={() => setStep(2)} className="btn-secondary"><ArrowLeft size={16} /> Back</button>
            <button onClick={handleNextFromStep3} className="btn-primary">Next: Review & Submit <ArrowRight size={16} /></button>
          </div>
        </div>
      )}

      {/* STEP 4: REVIEW & SUBMIT */}
      {step === 4 && (
        <div className="glass-panel" style={{ padding: '2rem', background: '#ffffff' }}>
          <h3 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.5rem' }}>Step 4 — Review Entered Details & Uploaded Documents</h3>
          <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
            Please review your entered details and attached documents below. Upon clicking <strong>Submit Claim</strong>, all details will be sent directly to the <strong>Service Center Module</strong>.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
            {/* Vehicle Card */}
            <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', padding: '1.25rem', borderRadius: 'var(--radius-md)' }}>
              <h4 style={{ fontWeight: 700, color: '#0284c7', fontSize: '0.9rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Car size={16} /> Selected Vehicle
              </h4>
              <p style={{ fontSize: '0.85rem', color: '#0f172a' }}><strong>{selectedVehicle?.make} {selectedVehicle?.model}</strong></p>
              <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Reg #: {selectedVehicle?.registration_number || 'N/A'}</p>
              <p style={{ fontSize: '0.8rem', color: '#64748b' }}>VIN / Chassis #: {selectedVehicle?.vin || 'Not provided'}</p>
              <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Engine #: {selectedVehicle?.engine_number || 'Not provided'}</p>
            </div>

            {/* Incident Card */}
            <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', padding: '1.25rem', borderRadius: 'var(--radius-md)' }}>
              <h4 style={{ fontWeight: 700, color: '#0284c7', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                Accident Information
              </h4>
              <p style={{ fontSize: '0.8rem', color: '#0f172a' }}><strong>Type:</strong> {accidentType}</p>
              <p style={{ fontSize: '0.8rem', color: '#0f172a' }}><strong>Date & Time:</strong> {accidentDate} @ {accidentTime}</p>
              <p style={{ fontSize: '0.8rem', color: '#0f172a' }}><strong>Location:</strong> {accidentLocation}</p>
            </div>

            {/* Policy Card */}
            <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', padding: '1.25rem', borderRadius: 'var(--radius-md)' }}>
              <h4 style={{ fontWeight: 700, color: '#0284c7', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                Policy & Insurance Details
              </h4>
              <p style={{ fontSize: '0.8rem', color: '#0f172a' }}><strong>Insurer:</strong> {insurerName}</p>
              <p style={{ fontSize: '0.8rem', color: '#0f172a' }}><strong>Policy #:</strong> {policyNo}</p>
              <p style={{ fontSize: '0.8rem', color: '#0f172a' }}><strong>Type:</strong> {policyType}</p>
            </div>

            {/* Description Card */}
            <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', padding: '1.25rem', borderRadius: 'var(--radius-md)' }}>
              <h4 style={{ fontWeight: 700, color: '#0284c7', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                Incident Description <span style={{ fontWeight: 400, color: '#64748b' }}>(Optional)</span>
              </h4>
              <p style={{ fontSize: '0.8rem', color: '#0f172a' }}>{description || 'None provided.'}</p>
            </div>

            <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', padding: '1.25rem', borderRadius: 'var(--radius-md)' }}>
              <h4 style={{ fontWeight: 700, color: '#0284c7', fontSize: '0.9rem', marginBottom: '0.5rem' }}>Customer Address</h4>
              <textarea
                value={customerAddress}
                onChange={(e) => setCustomerAddress(e.target.value)}
                placeholder="Enter your street address, city, state, postal code, and country"
                rows={3}
                style={{ width: '100%', padding: '0.65rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', resize: 'vertical' }}
              />
              <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.4rem' }}>This address will be included with the claim sent to the service center.</p>
            </div>
          </div>

          {/* Uploaded Mandatory Documents List */}
          <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', padding: '1.25rem', borderRadius: 'var(--radius-md)', marginBottom: '1.5rem' }}>
            <h4 style={{ fontWeight: 700, color: '#0369a1', fontSize: '0.95rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <FileText size={18} /> Mandatory Attached Documents for Service Center Queue
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ffffff', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #e0f2fe' }}>
                <span><strong>Policy Document:</strong> {policyDocFile ? policyDocFile.name : 'Missing'}</span>
                <span className={`badge ${policyDocFile ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '0.65rem' }}>
                  {policyDocFile ? 'ATTACHED' : 'REQUIRED'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ffffff', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #e0f2fe' }}>
                <span><strong>Registration Certificate (RC):</strong> {rcFile ? rcFile.name : 'Missing'}</span>
                <span className={`badge ${rcFile ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '0.65rem' }}>
                  {rcFile ? 'ATTACHED' : 'REQUIRED'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ffffff', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #e0f2fe' }}>
                <span><strong>Driving Licence (DL):</strong> {dlFile ? dlFile.name : 'Missing'}</span>
                <span className={`badge ${dlFile ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '0.65rem' }}>
                  {dlFile ? 'ATTACHED' : 'REQUIRED'}
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <button onClick={() => setStep(3)} className="btn-secondary"><ArrowLeft size={16} /> Edit Details</button>
            <button onClick={handleSubmitClaim} className="btn-primary" disabled={loading}>
              {loading ? 'Submitting to Service Center...' : 'SUBMIT TO SERVICE CENTER'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
