import {
  Bell, BookOpen, BookPlus, CalendarRange, ClipboardCheck, FileText, Gauge, Home, Inbox, LayoutDashboard, Library,
  ListChecks, ListTree, Map as MapIcon, Network, Scale, ScrollText, ShieldCheck, Target, Upload, UserCircle, UserPlus, Users, type LucideIcon,
} from 'lucide-react'

/** One icon per navigation entry (Lucide, DESIGN.md §4) - used by the menu and the home page tiles. */
export const NAV_ICON: Record<string, LucideIcon> = {
  '/': Home, '/account': UserCircle, '/notifications': Bell,
  '/learn': BookOpen, '/roadmap': MapIcon, '/courses': BookPlus, '/my-appeals': Scale,
  '/console': LayoutDashboard, '/reviews': Inbox, '/sources': Library, '/topics': ListTree, '/items': ListChecks, '/content': FileText, '/appeals': Scale,
  '/admin/curriculum': Upload, '/outcomes/review': ClipboardCheck, '/criteria': Target, '/mastery-policy': Gauge, '/mappings': Network,
  '/admin/users': Users, '/audit': ScrollText, '/admin/offerings': CalendarRange, '/ai': ShieldCheck, '/admin/enrollment': UserPlus,
}

/** One plain-language line per page, for the home page tiles. */
export const NAV_DESC: Record<string, string> = {
  '/notifications': 'Messages about reviews, appeals and your courses',
  '/learn': 'Your courses, lessons, quizzes and progress',
  '/roadmap': 'Which courses you take in each semester',
  '/courses': 'Browse courses and enrol in a section',
  '/my-appeals': 'Ask for a result to be looked at again',
  '/console': 'Class mastery, reviews waiting and learners needing help',
  '/reviews': 'AI drafts and requests waiting for your decision',
  '/sources': 'Optional reading the AI can cite',
  '/topics': 'A semester of topics per course, written into personal lessons',
  '/items': 'Diagnostic and practice questions per CLO',
  '/content': 'Lessons and notes for each unit',
  '/appeals': 'Student appeals to decide',
  '/admin/curriculum': 'Upload the CLO/PLO document and the roadmap',
  '/outcomes/review': 'Check and approve the extracted outcomes',
  '/criteria': 'The mastery target for each outcome',
  '/mastery-policy': 'How mastery is calculated',
  '/mappings': 'Link CLOs to PLOs and activate courses',
  '/admin/users': 'Accounts, roles and access',
  '/audit': 'Who changed what, and when',
  '/admin/offerings': 'Terms, sections and instructors',
  '/ai': 'AI use, limits and the call log',
  '/admin/enrollment': 'Enrol students and handle exceptions',
}
