import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { FleetPage } from './pages/FleetPage'
import { SystemDetailPage } from './pages/SystemDetailPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<FleetPage />} />
          <Route path="systems/:id" element={<SystemDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
