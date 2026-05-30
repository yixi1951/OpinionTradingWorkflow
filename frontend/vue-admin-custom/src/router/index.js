import { createRouter, createWebHistory } from 'vue-router'
import TradingDashboard from '../pages/TradingDashboard.vue'
import PlaceholderModule from '../pages/PlaceholderModule.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: TradingDashboard },
  { path: '/bigdata', name: 'BigDataView', component: PlaceholderModule },
  { path: '/freqtrade', name: 'Freqtrade', component: PlaceholderModule },
  { path: '/streamlit', name: 'Streamlit', component: PlaceholderModule },
  { path: '/realtime', name: 'Realtime', component: PlaceholderModule },
  { path: '/brand', name: 'Brand', component: PlaceholderModule }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
