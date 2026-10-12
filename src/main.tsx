import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { FluentProvider, createDarkTheme, type BrandVariants } from '@fluentui/react-components';
import '@fontsource/ibm-plex-sans-thai/400.css';
import '@fontsource/ibm-plex-sans-thai/500.css';
import '@fontsource/ibm-plex-sans-thai/600.css';
import '@fontsource/geist/400.css';
import '@fontsource/geist/500.css';
import '@fontsource/geist/600.css';
import '@fontsource/geist/700.css';
import '@fontsource/geist-mono/500.css';
import { Loading, WorldProvider } from './lib';
import './styles.css';
import { crewHost } from './urls';

// Fluent theme tokens: one shared theme for both product surfaces.
const brand: BrandVariants = { 10: '#031020', 20: '#08223a', 30: '#0b324f', 40: '#0c4164', 50: '#09517a', 60: '#086191', 70: '#1273a6', 80: '#2485bd', 90: '#3798d3', 100: '#53ace8', 110: '#6ebbf0', 120: '#8acbf5', 130: '#a6daf9', 140: '#c0e7fc', 150: '#daf2fd', 160: '#edf9fe' };
const theme = { ...createDarkTheme(brand), fontFamilyBase: '"IBM Plex Sans Thai", "Geist", sans-serif', colorNeutralBackground1: '#17202a', colorNeutralBackground2: '#121a23', colorNeutralBackground3: '#11171e', colorNeutralForeground1: '#e8eef5', colorNeutralForeground2: '#a9b8c8', colorBrandForeground1: '#6ebbf0' };
const Commander = React.lazy(() => import('./Commander'));
const CrewApp = React.lazy(() => import('./CrewApp'));
const CrewSelect = React.lazy(() => import('./CrewSelect'));
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><FluentProvider theme={theme}><BrowserRouter><WorldProvider><React.Suspense fallback={<Loading />}><Routes>
    <Route path="/commander" element={<Commander />} /><Route path="/crew/:crewId" element={<CrewApp />} />
    <Route path="/crew" element={<CrewSelect />} />
    <Route path="*" element={<Navigate to={crewHost ? '/crew' : '/commander'} replace />} />
  </Routes></React.Suspense></WorldProvider></BrowserRouter></FluentProvider></React.StrictMode>,
);
