import { useState } from "react"
import { Sidebar, SidebarView, VIEW_LABELS } from "@/components/ui/sidebar"
import { V0Chat } from "@/components/ui/v0-ai-chat"
import { FolderKanban, Search, Bot, Library } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Database, History } from "lucide-react"

// ---- Placeholder Views ----

function PlaceholderView({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
      <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
        {Icon}
      </div>
      <div>
        <h2 className="text-xl font-semibold text-foreground">{title}</h2>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
    </div>
  )
}

// ---- Main App ----

export default function App() {
  const [activeView, setActiveView] = useState<SidebarView>("tasks")
  const [activeConversationId, setActiveConversationId] = useState<string | undefined>(undefined)

  const handleViewChange = (view: SidebarView) => {
    setActiveView(view)
    setActiveConversationId(undefined)
  }

  const renderContent = () => {
    switch (activeView) {
      case "tasks":
        return (
          <V0Chat
            conversationId={activeConversationId}
            onConversationCreated={(id) => {
              setActiveConversationId(id)
            }}
          />
        )
      case "projects":
        return (
          <PlaceholderView
            icon={<FolderKanban className="w-8 h-8 text-muted-foreground" />}
            title="Project Management"
            description="Manage your projects and track progress"
          />
        )

      case "search":
        return (
          <PlaceholderView
            icon={<Search className="w-8 h-8 text-muted-foreground" />}
            title="Search"
            description="Search across all agent contexts and memories"
          />
        )

      case "agents":
        return (
          <PlaceholderView
            icon={<Bot className="w-8 h-8 text-muted-foreground" />}
            title="Agents"
            description="Configure and monitor your AI agent team"
          />
        )

      case "library":
        return (
          <PlaceholderView
            icon={<Library className="w-8 h-8 text-muted-foreground" />}
            title="Library"
            description="Browse shared context and knowledge base"
          />
        )

      default:
        return null
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        activeView={activeView}
        onViewChange={handleViewChange}
        pageTitle={VIEW_LABELS[activeView]}
      />

      <main className="flex-1 flex flex-col md:ml-[220px]">
        {/* Desktop Header */}
        <header className="hidden md:flex h-[52px] border-b border-border items-center px-5 gap-2 flex-shrink-0">
          <div className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
            <span>{VIEW_LABELS[activeView]}</span>
            <span className="opacity-40">/</span>
            <span className="text-foreground font-medium">新建任务</span>
          </div>
          <div className="ml-auto flex gap-1.5">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-3 text-[12px] text-muted-foreground border border-transparent hover:border-border hover:text-foreground gap-1.5"
            >
              <Database className="w-3 h-3" />
              接入数据源
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-3 text-[12px] text-muted-foreground border border-transparent hover:border-border hover:text-foreground gap-1.5"
            >
              <History className="w-3 h-3" />
              任务历史
            </Button>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-hidden pt-[52px] md:pt-[52px]">
          {renderContent()}
        </div>
      </main>
    </div>
  )
}
