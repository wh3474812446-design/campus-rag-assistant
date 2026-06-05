# 在桌面创建指向 start.bat 的快捷方式（双击即启动 RAG 知识库网站）
$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$dir = $PSScriptRoot
$lnk = Join-Path $desktop 'RAG 知识库.lnk'
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = Join-Path $dir 'start.bat'
$sc.WorkingDirectory = $dir
$sc.IconLocation = 'shell32.dll,13'
$sc.Description = 'RAG 知识库 - 本地文档问答助手'
$sc.Save()
Write-Output ('[OK] 已创建桌面快捷方式: ' + $lnk)