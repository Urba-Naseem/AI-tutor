// Central route table: each feature registers its pages here.
// `nav` puts the page in the sidebar for the listed roles.
import { lazy, Suspense, type ReactElement } from 'react'
import { Loading } from './components/ui'
import type { Role } from './auth/AuthContext'
import AccountPage from './pages/AccountPage'
import HomePage from './pages/HomePage'
import UsersPage from './pages/admin/UsersPage'
import AuditPage from './pages/admin/AuditPage'
import CurriculumPage from './pages/admin/CurriculumPage'
import OutcomeReviewPage from './pages/admin/OutcomeReviewPage'
import OfferingsPage from './pages/admin/OfferingsPage'
import CriteriaPage from './pages/admin/CriteriaPage'
import MasteryPolicyPage from './pages/admin/MasteryPolicyPage'
import SourcesPage from './pages/staff/SourcesPage'
import AIGovernancePage from './pages/admin/AIGovernancePage'
import ReviewQueuePage from './pages/staff/ReviewQueuePage'
import MappingsPage from './pages/staff/MappingsPage'
import CatalogPage from './pages/student/CatalogPage'
import RoadmapPage from './pages/student/RoadmapPage'
import EnrollmentAdminPage from './pages/admin/EnrollmentAdminPage'
import ItemBankPage from './pages/staff/ItemBankPage'
import ContentStudioPage from './pages/staff/ContentStudioPage'
import DiagnosticPage from './pages/student/DiagnosticPage'
import { MyLearningPage } from './pages/student/LearnPages'
import QuizReviewPage from './pages/student/QuizReviewPage'
import PathPage from './pages/student/PathPage'
import UnitPage, { UnitListPage } from './pages/student/UnitPage'
import QuizPage, { PracticeHubPage } from './pages/student/QuizPage'
import './pages/student/HintPanel'
import ReteachPage from './pages/student/ReteachPage'
import { ConsoleStudentPage, LegacyConsoleStudentRedirect } from './pages/staff/ConsolePages'
import './pages/staff/InterventionPanel'
import './pages/staff/PathControlPanel'
import './pages/staff/StudentLessonsPanel'
import ProgressPage from './pages/student/ProgressPage'
import { AppealReviewPage, NotificationsPage, StudentAppealsPage } from './pages/AppealsPages'
// @imports-end

export type AppRoute = {
  path: string
  element: ReactElement
  roles: Role[]
  nav?: string
  group?: string
}

const StyleguidePage = lazy(() => import('./pages/StyleguidePage'))
const CoursePage = lazy(() => import('./pages/student/CoursePage'))
const ConsoleCourse = lazy(() => import('./pages/staff/ConsoleCourse'))
const TopicPage = lazy(() => import('./pages/student/TopicPage'))
const ReadingPage = lazy(() => import('./pages/student/ReadingPage'))
const TopicsPage = lazy(() => import('./pages/staff/TopicsPage'))
const ConsoleHome = lazy(() => import('./pages/staff/ConsoleCourse').then((m) => ({ default: m.ConsoleHome })))

const ALL: Role[] = ['student', 'instructor', 'admin', 'exam_staff']
const STAFF: Role[] = ['instructor', 'admin']
/** Teaching work (sources, content, questions, console, reviews, appeals, mappings) is the instructor's alone. */
const TEACH: Role[] = ['instructor']

export const routes: AppRoute[] = [
  { path: '/', element: <HomePage />, roles: ALL, nav: 'Home', group: 'General' },
  { path: '/account', element: <AccountPage />, roles: ALL, nav: 'My account', group: 'General' },
  { path: '/admin/users', element: <UsersPage />, roles: ['admin'], nav: 'Users & roles', group: 'Administration' },
  { path: '/audit', element: <AuditPage />, roles: ['admin', 'exam_staff'], nav: 'Audit log', group: 'Administration' },
  { path: '/admin/curriculum', element: <CurriculumPage />, roles: ['admin'], nav: 'Curriculum upload', group: 'Curriculum' },
  { path: '/outcomes/review', element: <OutcomeReviewPage />, roles: STAFF, nav: 'Outcome review', group: 'Curriculum' },
  { path: '/outcomes/review/:vid', element: <OutcomeReviewPage />, roles: STAFF },
  { path: '/admin/offerings', element: <OfferingsPage />, roles: ['admin'], nav: 'Offerings & faculty', group: 'Administration' },
  { path: '/criteria', element: <CriteriaPage />, roles: ['admin', 'instructor', 'exam_staff'], nav: 'Attainment criteria', group: 'Curriculum' },
  { path: '/mastery-policy', element: <MasteryPolicyPage />, roles: ['admin', 'instructor', 'exam_staff'], nav: 'Mastery rules', group: 'Curriculum' },
  { path: '/sources', element: <SourcesPage />, roles: TEACH, nav: 'Suggested reading', group: 'Teaching' },
  { path: '/ai', element: <AIGovernancePage />, roles: ['admin', 'exam_staff'], nav: 'AI governance', group: 'Administration' },
  { path: '/reviews', element: <ReviewQueuePage />, roles: TEACH, nav: 'Review queue', group: 'Teaching' },
  { path: '/mappings', element: <MappingsPage />, roles: TEACH, nav: 'Mappings & activation', group: 'Curriculum' },
  { path: '/roadmap', element: <RoadmapPage />, roles: ['student'], nav: 'My roadmap', group: 'Learning' },
  { path: '/courses', element: <CatalogPage />, roles: ['student'], nav: 'Courses & enrolment', group: 'Learning' },
  { path: '/admin/enrollment', element: <EnrollmentAdminPage />, roles: ['admin'], nav: 'Enrolment', group: 'Administration' },
  { path: '/items', element: <ItemBankPage />, roles: TEACH, nav: 'Item bank', group: 'Teaching' },
  { path: '/topics', element: <Suspense fallback={<Loading />}><TopicsPage /></Suspense>, roles: TEACH, nav: 'Course topics', group: 'Teaching' },
  { path: '/content', element: <ContentStudioPage />, roles: TEACH, nav: 'Learning content', group: 'Teaching' },
  { path: '/learn', element: <MyLearningPage />, roles: ['student'], nav: 'My learning', group: 'Learning' },
  { path: '/learn/:courseId', element: <Suspense fallback={<Loading variant="cards" />}><CoursePage /></Suspense>, roles: ['student'] },
  { path: '/learn/:courseId/diagnostic', element: <DiagnosticPage />, roles: ['student'] },
  { path: '/learn/:courseId/path', element: <PathPage />, roles: ['student'] },
  { path: '/learn/:courseId/units', element: <UnitListPage />, roles: ['student'] },
  { path: '/learn/:courseId/unit/:unitId', element: <UnitPage />, roles: ['student'] },
  { path: '/learn/:courseId/topic/:topicId', element: <Suspense fallback={<Loading />}><TopicPage /></Suspense>, roles: ['student'] },
  { path: '/learn/:courseId/reading', element: <Suspense fallback={<Loading />}><ReadingPage /></Suspense>, roles: ['student'] },
  { path: '/learn/:courseId/practice', element: <PracticeHubPage />, roles: ['student'] },
  { path: '/learn/:courseId/quiz/:cloId', element: <QuizPage />, roles: ['student'] },
  { path: '/learn/:courseId/reteach/:cloId', element: <ReteachPage />, roles: ['student'] },
  { path: '/console', element: <Suspense fallback={<Loading variant="cards" />}><ConsoleHome /></Suspense>, roles: TEACH, nav: 'Instructor console', group: 'Teaching' },
  { path: '/console/:courseId', element: <Suspense fallback={<Loading variant="cards" />}><ConsoleCourse /></Suspense>, roles: TEACH },
  { path: '/console/:courseId/student', element: <ConsoleStudentPage />, roles: TEACH },
  { path: '/console/:courseId/student/:studentId', element: <LegacyConsoleStudentRedirect />, roles: TEACH },
  { path: '/learn/:courseId/progress', element: <ProgressPage />, roles: ['student'] },
  { path: '/notifications', element: <NotificationsPage />, roles: ALL, nav: 'Notifications', group: 'General' },
  { path: '/my-appeals', element: <StudentAppealsPage />, roles: ['student'], nav: 'Appeals', group: 'Learning' },
  { path: '/appeals', element: <AppealReviewPage />, roles: TEACH, nav: 'Appeals', group: 'Teaching' },
  // TEMPORARY design review page (brief step 3); loaded on demand so its chart library stays out of the main bundle
  { path: '/styleguide', element: <Suspense fallback={<Loading />}><StyleguidePage /></Suspense>, roles: ALL },
  { path: '/learn/:courseId/quiz-review/:aid', element: <QuizReviewPage />, roles: ['student'] },
  // @routes-end
]
