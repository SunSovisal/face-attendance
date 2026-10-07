import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore, type Me } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import WaitingView from '../views/WaitingView.vue'
import LiveView from '../views/LiveView.vue'
import EmployeesView from '../views/EmployeesView.vue'
import AttendanceView from '../views/AttendanceView.vue'
import LeaveView from '../views/LeaveView.vue'
import HolidaysView from '../views/HolidaysView.vue'
import AccountsView from '../views/AccountsView.vue'
import OfficeView from '../views/OfficeView.vue'
import TodayView from '../views/TodayView.vue'
import MonthView from '../views/MonthView.vue'
import PasswordView from '../views/PasswordView.vue'

export function homeFor(me: Me) {
  if (me.status !== 'active') return '/waiting'
  if (me.role === 'employee') return '/me'
  return '/live'
}

const staff = ['admin', 'super_admin']

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/register', component: RegisterView, meta: { public: true } },
    { path: '/waiting', component: WaitingView },
    { path: '/password', component: PasswordView },
    { path: '/', redirect: '/live' },
    { path: '/live', component: LiveView, meta: { roles: staff } },
    { path: '/today', component: TodayView, meta: { roles: staff } },
    { path: '/attendance', component: AttendanceView, meta: { roles: staff } },
    { path: '/month', component: MonthView, meta: { roles: staff } },
    { path: '/employees', component: EmployeesView, meta: { roles: staff } },
    { path: '/me', component: AttendanceView },
    { path: '/leave', component: LeaveView },
    { path: '/holidays', component: HolidaysView, meta: { roles: staff } },
    { path: '/accounts', component: AccountsView, meta: { roles: ['super_admin'] } },
    { path: '/office', component: OfficeView, meta: { roles: ['super_admin'] } },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.fetchMe()
  const me = auth.me
  if (to.meta.public) {
    if (me) return homeFor(me)
    return true
  }
  if (!me) return '/login'
  if (me.status !== 'active') return to.path === '/waiting' || to.path === '/password' ? true : '/waiting'
  if (to.path === '/waiting') return homeFor(me)
  const roles = to.meta.roles as string[] | undefined
  if (roles && !roles.includes(me.role)) return homeFor(me)
  return true
})

export default router
