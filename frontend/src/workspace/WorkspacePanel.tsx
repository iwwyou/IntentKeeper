import Editor from '@monaco-editor/react'
import { useStore } from '../state/store'
import { registerSolidity } from '../editor/solidity'
import FileExplorer from './FileExplorer'
import DepsSidebar from './DepsSidebar'
import FunctionList from './FunctionList'

// 디바운스: 편집 → 잠시 후 분석 트리거 (백엔드 live 분석 흉내)
let timer: ReturnType<typeof setTimeout> | undefined

export default function WorkspacePanel() {
  const files = useStore((s) => s.files)
  const activeFile = useStore((s) => s.activeFile)
  const updateActiveContent = useStore((s) => s.updateActiveContent)

  const content = files.find((f) => f.path === activeFile)?.content ?? ''

  return (
    <div className="workspace">
      <div className="left-sidebar">
        <FileExplorer />
        <DepsSidebar />
      </div>

      <div className="editor-wrap">
        {activeFile ? (
          <Editor
            height="100%"
            path={activeFile} /* 파일별 모델 → undo 스택 분리 */
            language="solidity"
            theme="iqdebug-dark"
            beforeMount={registerSolidity}
            value={content}
            onChange={(val) => {
              if (timer) clearTimeout(timer)
              timer = setTimeout(() => updateActiveContent(val ?? ''), 400)
            }}
            options={{ minimap: { enabled: false }, fontSize: 13 }}
          />
        ) : (
          <div style={{ padding: 24, color: '#888' }}>파일 없음 — + new 로 생성</div>
        )}
      </div>

      <FunctionList />
    </div>
  )
}
