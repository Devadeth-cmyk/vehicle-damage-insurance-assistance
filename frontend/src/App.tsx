import React, { useState, useEffect } from 'react';
import { AuthModal } from './AuthModal';
import { UserLayout } from './UserLayout';
import { UserDashboard } from './UserDashboard';
import { MyVehicles } from './MyVehicles';
import { AddVehicle } from './AddVehicle';
import { NewClaimWizard } from './NewClaimWizard';
import { ClaimsModule } from './ClaimsModule';
import { ClaimDetailsView } from './ClaimDetailsView';
import { InsuranceAssistantPage } from './InsuranceAssistantPage';
import { AssessmentResultsView } from './AssessmentResultsView';
import { ClaimPackageView } from './ClaimPackageView';
import { UserProfileView } from './SecondaryUserViews';
import { api, type User, type Vehicle, type Claim } from './api';

import { ServiceCenterPortal } from './ServiceCenterPortal';

export const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentRoute, setCurrentRoute] = useState<string>('/dashboard');
  const [portalMode, setPortalMode] = useState<'customer' | 'service_center'>('customer');

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const res = await api.get('/users/me');
        setUser(res.data);
        if (res.data.role && ['service_center', 'admin'].includes(res.data.role.toLowerCase())) {
          setPortalMode('service_center');
        }
        fetchUserData();
      } catch (err) {
        localStorage.removeItem('token');
      }
    }
    setLoading(false);
  };

  const fetchUserData = async () => {
    try {
      const vehRes = await api.get('/vehicles');
      setVehicles(vehRes.data);

      const claimsRes = await api.get('/claims');
      setClaims(claimsRes.data);
    } catch (err) {
      console.error('Failed to load user vehicles & claims', err);
    }
  };

  // Synchronize browser URL with module route
  const navigateToRoute = (route: string) => {
    let targetPath = route;
    if (portalMode === 'service_center') {
      targetPath = route.startsWith('/service-center') ? route : `/service-center${route}`;
    } else {
      targetPath = route.startsWith('/customer') ? route : `/customer${route}`;
    }
    window.history.pushState({}, '', targetPath);
    setCurrentRoute(route);
  };

  useEffect(() => {
    const handlePopState = () => {
      const pathname = window.location.pathname;
      if (pathname.startsWith('/service-center')) {
        setPortalMode('service_center');
        const sub = pathname.replace('/service-center', '') || '/dashboard';
        setCurrentRoute(sub);
      } else if (pathname.startsWith('/customer')) {
        setPortalMode('customer');
        const sub = pathname.replace('/customer', '') || '/dashboard';
        setCurrentRoute(sub);
      } else {
        // default fallback if they navigate to /
        setCurrentRoute('/dashboard');
      }
    };

    // run once on mount
    handlePopState();

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    if (user) {
      const basePrefix = portalMode === 'service_center' ? '/service-center' : '/customer';
      const cleanSub = currentRoute.startsWith('/') ? currentRoute : `/${currentRoute}`;
      const targetPath = `${basePrefix}${cleanSub}`;
      if (window.location.pathname !== targetPath) {
        window.history.replaceState({}, '', targetPath);
      }
    }
  }, [portalMode, currentRoute, user]);

  const handleLoginSuccess = (userData: User) => {
    setUser(userData);
    fetchUserData();
    if (userData.role && ['service_center', 'admin'].includes(userData.role.toLowerCase())) {
      setPortalMode('service_center');
      window.history.pushState({}, '', '/service-center/dashboard');
    } else {
      setPortalMode('customer');
      window.history.pushState({}, '', '/customer/dashboard');
    }
    setCurrentRoute('/dashboard');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setUser(null);
    window.history.pushState({}, '', '/customer');
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
        Loading AutoInsight Insurance Portal...
      </div>
    );
  }

  if (!user) {
    return <AuthModal onLoginSuccess={handleLoginSuccess} />;
  }

  if (portalMode === 'service_center') {
    return <ServiceCenterPortal user={user} currentRoute={currentRoute} onNavigate={navigateToRoute} onLogout={handleLogout} />;
  }

  return (
    <UserLayout
      user={user}
      currentRoute={currentRoute}
      onNavigate={navigateToRoute}
      onLogout={handleLogout}
    >
      {currentRoute === '/dashboard' && (
        <UserDashboard user={user} vehicles={vehicles} claims={claims} onNavigate={navigateToRoute} />
      )}

      {currentRoute === '/vehicles' && (
        <MyVehicles vehicles={vehicles} onNavigate={navigateToRoute} onVehicleUpdated={fetchUserData} />
      )}

      {currentRoute === '/vehicles/add' && (
        <AddVehicle onNavigate={navigateToRoute} onVehicleAdded={fetchUserData} />
      )}

      {currentRoute === '/claims/new' && (
        <NewClaimWizard
          vehicles={vehicles}
          user={user}
          onNavigate={navigateToRoute}
          onClaimSubmitted={(claim) => {
            setClaims((current) => [claim, ...current.filter((item) => item.claim_id !== claim.claim_id)]);
            fetchUserData();
          }}
        />
      )}

      {currentRoute === '/claims' && (
        <ClaimsModule
          claims={claims}
          vehicles={vehicles}
          onNavigate={navigateToRoute}
          onClaimCreated={fetchUserData}
        />
      )}

      {currentRoute.startsWith('/claims/') && currentRoute !== '/claims/new' && (
        <ClaimDetailsView
          claimId={currentRoute.replace('/claims/', '')}
          claims={claims}
          user={user}
          onNavigate={navigateToRoute}
        />
      )}

      {currentRoute === '/assessment' && (
        <AssessmentResultsView claims={claims} onNavigate={navigateToRoute} />
      )}

      {currentRoute === '/package' && (
        <ClaimPackageView claims={claims} onNavigate={navigateToRoute} />
      )}

      {currentRoute === '/assistant' && <InsuranceAssistantPage />}
      {currentRoute === '/profile' && <UserProfileView user={user} />}
    </UserLayout>
  );
};

export default App;
