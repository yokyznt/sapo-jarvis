param([string]$out,[int]$x=0,[int]$y=-1080,[int]$w=1920,[int]$h=1080)
Add-Type -AssemblyName System.Drawing
$b=New-Object Drawing.Bitmap $w,$h
$g=[Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen($x,$y,0,0,(New-Object Drawing.Size $w,$h))
$b.Save($out)
