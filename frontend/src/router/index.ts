import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import LiveView from '../views/LiveView.vue'
import PeopleView from '../views/PeopleView.vue'
import AttendanceView from '../views/AttendanceView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/', redirect: '/live' },
    { path: '/live', component: LiveView },
    { path: '/people', component: PeopleView },
    { path: '/attendance', component: AttendanceView },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.fetchMe()
  if (to.meta.public) {
    if (auth.me) return '/live'
    return true
  }
  if (!auth.me) return '/login'
  return true
})

export default router
