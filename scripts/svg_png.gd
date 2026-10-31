extends SceneTree


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var svg := FileAccess.get_file_as_string(args[0])
	var out_dir: String = args[1]
	for s in args.slice(2):
		var size := int(s)
		var probe := Image.new()
		probe.load_svg_from_string(svg, 1.0)
		var scale: float = float(size) / max(probe.get_width(), probe.get_height())
		var img := Image.new()
		img.load_svg_from_string(svg, scale)
		var square := Image.create(size, size, false, Image.FORMAT_RGBA8)
		square.fill(Color(0, 0, 0, 0))
		var w := mini(img.get_width(), size)
		var h := mini(img.get_height(), size)
		square.blit_rect(img, Rect2i(0, 0, w, h), Vector2i((size - w) / 2, (size - h) / 2))
		square.save_png(out_dir.path_join("icon_%d.png" % size))
	quit()
