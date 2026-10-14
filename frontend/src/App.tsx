import React, { useState, useEffect } from 'react';
import { AuthModal } from './AuthModal';
import { UserLayout } from './UserLayout';
import { UserDashboard } from './UserDashboard';
import { MyVehicles } from './MyVehicles';
import { AddVehicle } from './AddVehicle';
import { VehicleDetailsView } from './VehicleDetailsView';
import { NewClaimWizard } from './NewClaimWizard';
import { ClaimsModule } from './ClaimsModule';
import { ClaimDetailsView } from './ClaimDetailsView';
import { InsuranceAssistantPage } from './InsuranceAssistantPage';
import { AssessmentResultsView } from './AssessmentResultsView';
import { ClaimPackageView } from './ClaimPackageView';
import { UserProfileView } from './SecondaryUserViews';
import { api, type User, type Vehicle, type Claim } from './api';

import { ServiceCenterPortal } from './ServiceCenterPortal';
import { AdminPortal } from './AdminPortal';

type PortalMode = 'customer' | 'service_center' | 'admin';

// The customer, service-center, and platform-admin apps use separate ports.
// A build can override this with VITE_PORTAL_MODE for separate deployments.
const getAppPortal = (): PortalMode => {
  const configuredPortal = import.meta.env.VITE_PORTAL_MODE?.toLowerCase();
  if (configuredPortal === 'admin') return 'admin';
  if (configuredPortal === 'service_center') return 'service_center';
  if (configuredPortal === 'customer') return 'customer';
  if (window.location.port === '5175') return 'admin';
  return window.location.port === '5174' ? 'service_center' : 'customer';
};

const appPortal = getAppPortal();
const portalBasePath = appPortal === 'service_center' ? '/service-center' : appPortal === 'admin' ? '/admin' : '/customer';

const roleToPortal = (role?: string): PortalMode => {
  if (role?.toLowerCase() === 'admin') return 'admin';
  return role?.toLowerCase() === 'service_center' ? 'service_center' : 'customer';
};

export const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentRoute, setCurrentRoute] = useState<string>('/dashboard');
  const portalMode = appPortal;

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
        const actualPortal = roleToPortal(res.data.role);
        if (actualPortal !== appPortal) {
          localStorage.removeItem('token');
        } else {
          setUser(res.data);
          if (appPortal === 'customer') fetchUserData();
        }
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
    if (portalMode === 'admin') {
      targetPath = route.startsWith('/admin') ? route : `/admin${route}`;
    } else if (portalMode === 'service_center') {
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
      if (loading) return;
      if (!user) {
        const loginPath = `${portalBasePath}/login`;
        if (pathname !== loginPath) window.history.replaceState({}, '', loginPath);
        return;
      }

      const actualPortal = roleToPortal(user.role);
      if (actualPortal !== appPortal) {
        localStorage.removeItem('token');
        setUser(null);
        window.history.replaceState({}, '', `${portalBasePath}/login`);
        return;
      }
      if (!pathname.startsWith(portalBasePath)) {
        window.history.replaceState({}, '', `${portalBasePath}/dashboard`);
        setCurrentRoute('/dashboard');
        return;
      }
      const subRoute = pathname.replace(portalBasePath, '') || '/dashboard';
      if (subRoute === '/login' || subRoute === '/') {
        window.history.replaceState({}, '', `${portalBasePath}/dashboard`);
        setCurrentRoute('/dashboard');
      } else {
        setCurrentRoute(subRoute);
      }
    };

    // run once on mount
    handlePopState();

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [user, loading]);

  useEffect(() => {
    if (user) {
      const cleanSub = currentRoute.startsWith('/') ? currentRoute : `/${currentRoute}`;
      const targetPath = `${portalBasePath}${cleanSub}`;
      if (window.location.pathname !== targetPath) {
        window.history.replaceState({}, '', targetPath);
      }
    }
  }, [portalMode, currentRoute, user]);

  const handleLoginSuccess = (userData: User) => {
    if (roleToPortal(userData.role) !== appPortal) {
      localStorage.removeItem('token');
      return;
    }
    setUser(userData);
    if (appPortal === 'customer') fetchUserData();
    window.history.pushState({}, '', `${portalBasePath}/dashboard`);
    setCurrentRoute('/dashboard');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setUser(null);
    window.history.pushState({}, '', `${portalBasePath}/login`);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
        Loading AutoInsight Insurance Portal...
      </div>
    );
  }

  if (!user) {
    return <AuthModal portal={appPortal} onLoginSuccess={handleLoginSuccess} />;
  }

  if (portalMode === 'admin') {
    return <AdminPortal user={user} currentRoute={currentRoute} onNavigate={navigateToRoute} onLogout={handleLogout} />;
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

      {currentRoute.match(/^\/vehicles\/\d+\/edit$/) && (() => {
        const vehicleId = Number(currentRoute.split('/')[2]);
        const vehicle = vehicles.find((item) => item.id === vehicleId);
        return vehicle ? (
          <AddVehicle vehicle={vehicle} onNavigate={navigateToRoute} onVehicleAdded={fetchUserData} />
        ) : (
          <div role="alert" style={{ padding: '1.5rem', color: '#b91c1c', background: '#fef2f2', borderRadius: '0.75rem' }}>
            Vehicle not found. <button className="btn-secondary" onClick={() => navigateToRoute('/vehicles')}>Back to vehicles</button>
          </div>
        );
      })()}

      {currentRoute.match(/^\/vehicles\/\d+$/) && (
        <VehicleDetailsView
          vehicle={vehicles.find((vehicle) => vehicle.id === Number(currentRoute.split('/')[2]))}
          onNavigate={navigateToRoute}
        />
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
