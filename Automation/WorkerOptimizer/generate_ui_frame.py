"""Author mod-owned tintable UI frame/shadow masks; no runtime code or game data."""
from pathlib import Path
import math
import struct
import zlib

ROOT='/Game/Mods/WorkerOptimizer'
STATUS_ASSETS={'completed':'T_WorkerOptimizerStatusCompleted','problems':'T_WorkerOptimizerStatusProblems',
               'error':'T_WorkerOptimizerStatusError','aborted':'T_WorkerOptimizerStatusAborted'}
ICON_ASSETS={'own':'T_WorkerOptimizerPriorityOwn','inherited':'T_WorkerOptimizerPriorityInherited'}
ASSETS=(('T_WorkerOptimizerFrame',16,6/16),('T_WorkerOptimizerShadow',64,24/64))+tuple((name,32,0) for name in (*STATUS_ASSETS.values(),*ICON_ASSETS.values()))

def rounded_distance(x,y,half=8.0,radius=6.0):
    qx,qy=abs(x)-(half-radius),abs(y)-(half-radius)
    return math.hypot(max(qx,0.0),max(qy,0.0))+min(max(qx,qy),0.0)-radius

def mask_pixels(width,coverage):
    pixels=bytearray()
    for y in range(width):
        for x in range(width):
            value=sum(coverage(x+(sx+.5)/4,y+(sy+.5)/4) for sy in range(4) for sx in range(4))/16
            pixels.extend((255,255,255,round(255*max(0.0,min(1.0,value)))))
    return bytes(pixels)

def frame_pixels():
    return mask_pixels(16,lambda x,y:float(rounded_distance(x-8,y-8)<=0))

def shadow_pixels():
    def coverage(x,y):
        # Compact smooth support, not a Gaussian claim: 16px core + 24px falloff.
        t=max(0.0,min(1.0,rounded_distance(x-32,y-32)/24.0))
        return 1.0-t*t*(3.0-2.0*t)
    return mask_pixels(64,coverage)

def segment_distance(x,y,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0.0,min(1.0,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)

def inside_polygon(x,y,vertices):
    return all((b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])>=0 for a,b in zip(vertices,vertices[1:]+vertices[:1]))

def status_pixels(status):
    assert status in STATUS_ASSETS
    triangle=((16,2),(30,29),(2,29))
    octagon=((10,2),(22,2),(30,10),(30,22),(22,30),(10,30),(2,22),(2,10))
    def coverage(x,y):
        radius=math.hypot(x-16,y-16)
        if status=='completed':
            check=min(segment_distance(x,y,(8,16),(14,22)),segment_distance(x,y,(14,22),(24,10)))<=1.7
            return float(radius<=14 and not check)
        if status=='problems':
            detail=(abs(x-16)<=1.7 and 10<=y<=20) or math.hypot(x-16,y-24)<=1.7
            return float(inside_polygon(x,y,triangle) and not detail)
        if status=='error':
            cross=min(segment_distance(x,y,(10,10),(22,22)),segment_distance(x,y,(22,10),(10,22)))<=1.7
            return float(inside_polygon(x,y,octagon) and not cross)
        slash=segment_distance(x,y,(7,25),(25,7))<=1.7
        return float(radius<=14 and (radius>=10.5 or slash))
    return mask_pixels(32,coverage)

def priority_pixels(kind):
    assert kind in ICON_ASSETS
    def coverage(x,y):
        if kind=='own':
            head=10<=x<=22 and 3<=y<=7
            stem=12<=x<=20 and 7<=y<=13
            shoulder=inside_polygon(x,y,((12,12),(20,12),(26,18),(6,18)))
            needle=15<=x<=17 and 18<=y<=29
            return float(head or stem or shoulder or needle)
        segments=(((7,4),(7,17)),((7,17),(25,17)),((19,11),(25,17)),((25,17),(19,23)))
        return float(min(segment_distance(x,y,a,b) for a,b in segments)<=1.7)
    return mask_pixels(32,coverage)

def png_bytes(width,height,pixels):
    assert len(pixels)==width*height*4
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    rows=b''.join(b'\0'+pixels[y*width*4:(y+1)*width*4] for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(rows,9))+chunk(b'IEND',b'')

def validate_assets():
    import unreal
    for name,size,margin in ASSETS:
        asset=unreal.load_asset(ROOT+'/'+name)
        assert isinstance(asset,unreal.Texture2D),name
        assert asset.blueprint_get_size_x()==size and asset.blueprint_get_size_y()==size,name
        assert asset.get_editor_property('compression_settings')==unreal.TextureCompressionSettings.TC_EDITOR_ICON
        assert asset.get_editor_property('lod_group')==unreal.TextureGroup.TEXTUREGROUP_UI
        assert asset.get_editor_property('mip_gen_settings')==unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS
        assert asset.get_editor_property('srgb')
        # The resource and margin are consumable by native nine-slice Slate brushes.
        brush=unreal.SlateBrush()
        brush.set_editor_property('resource_object',asset)
        brush.set_editor_property('draw_as',unreal.SlateBrushDrawType.BOX if margin else unreal.SlateBrushDrawType.IMAGE)
        brush.set_editor_property('margin',unreal.Margin(margin,margin,margin,margin))
        assert brush.get_editor_property('resource_object')==asset
    unreal.log('WO_UI_FRAME_ASSETS_PASS: native frame/shadow, four status and two priority masks, UI RGBA, sRGB, no mips and brush resources')

def generate():
    import unreal
    directory=Path(unreal.Paths.project_saved_dir())/'WorkerOptimizerUIAssets'
    directory.mkdir(parents=True,exist_ok=True)
    tasks=[]
    pixels_by_asset=(frame_pixels(),shadow_pixels(),*(status_pixels(status) for status in STATUS_ASSETS),*(priority_pixels(kind) for kind in ICON_ASSETS))
    for (name,size,_),pixels in zip(ASSETS,pixels_by_asset):
        filename=directory/(name+'.png')
        filename.write_bytes(png_bytes(size,size,pixels))
        task=unreal.AssetImportTask()
        task.set_editor_property('filename',str(filename))
        task.set_editor_property('destination_path',ROOT)
        task.set_editor_property('destination_name',name)
        task.set_editor_property('automated',True)
        task.set_editor_property('replace_existing',True)
        task.set_editor_property('save',False)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    for name,_,_ in ASSETS:
        asset=unreal.load_asset(ROOT+'/'+name)
        assert isinstance(asset,unreal.Texture2D),name
        asset.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_EDITOR_ICON)
        asset.set_editor_property('lod_group',unreal.TextureGroup.TEXTUREGROUP_UI)
        asset.set_editor_property('mip_gen_settings',unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        asset.set_editor_property('srgb',True)
        asset.set_editor_property('filter',unreal.TextureFilter.TF_BILINEAR)
        assert unreal.EditorAssetLibrary.save_loaded_asset(asset)
    validate_assets()
    unreal.log('WO_UI_FRAME_GENERATED')

if __name__=='__main__':
    generate()
