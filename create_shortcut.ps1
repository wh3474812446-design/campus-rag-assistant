# 在项目文件夹内创建指向 start.bat 的快捷方式（双击即一键启动：先起后端→等就绪→再开前端→自动打开网页配 API）
$ws = New-Object -ComObject WScript.Shell
$dir = $PSScriptRoot
$lnk = Join-Path $dir '一键启动 RAG 知识库.lnk'
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = Join-Path $dir 'start.bat'
$sc.WorkingDirectory = $dir
$sc.IconLocation = 'shell32.dll,13'
$sc.Description = 'RAG 知识库 - 一键启动（前后端一起开，打开网页后右上角配 API Key）'
$sc.Save()
Write-Output ('[OK] 已在项目文件夹内创建快捷方式: ' + $lnk)