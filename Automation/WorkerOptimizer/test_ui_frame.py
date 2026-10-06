"""Small procedural alpha-mask checks, plus optional native imported-asset checks."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from generate_ui_frame import frame_pixels, shadow_pixels, status_pixels, priority_pixels, png_bytes, validate_assets, STATUS_ASSETS

def run_source():
    frame=frame_pixels()
    shadow=shadow_pixels()
    assert len(frame)==16*16*4 and len(shadow)==64*64*4
    alpha=lambda pixels,width,x,y:pixels[(y*width+x)*4+3]
    assert alpha(frame,16,0,0)==0
    assert alpha(frame,16,8,8)==255
    assert any(0<frame[i]<255 for i in range(3,len(frame),4)), 'Frame corners must be anti-aliased'
    assert alpha(shadow,64,32,32)==255
    assert alpha(shadow,64,0,0)==0
    assert alpha(shadow,64,32,3)<alpha(shadow,64,32,12)<alpha(shadow,64,32,23)
    for pixels,width in ((frame,16),(shadow,64)):
        assert all(pixels[i]==255 for i in range(len(pixels)) if i%4!=3), 'Masks are tintable white RGBA'
        assert all(alpha(pixels,width,x,y)==alpha(pixels,width,width-1-x,y)==alpha(pixels,width,x,width-1-y) for y in range(width) for x in range(width))
        encoded=png_bytes(width,width,pixels)
        assert encoded.startswith(b'\x89PNG\r\n\x1a\n')
    print('WO_UI_FRAME_SOURCE_PASS')
    icons=[status_pixels(status) for status in ('completed','problems','error','aborted')]
    assert len(set(icons))==4
    for pixels in icons:
        assert len(pixels)==32*32*4
        assert pixels[3]==0 and max(pixels[3::4])==255
        assert any(0<value<255 for value in pixels[3::4])
        assert all(pixels[i]==255 for i in range(len(pixels)) if i%4!=3)
    print('WO_UI_STATUS_ICONS_SOURCE_PASS')
    priority_icons=[priority_pixels(kind) for kind in ('own','inherited')]
    assert priority_icons[0]!=priority_icons[1]
    assert all(len(pixels)==32*32*4 and max(pixels[3::4])==255 for pixels in priority_icons)
    print('WO_UI_PRIORITY_ICONS_SOURCE_PASS')

def run_native_frames():
    import unreal
    tools=unreal.get_default_object(unreal.UMGToolSet)
    def widget(asset,name):
        blueprint=unreal.load_asset('/Game/Mods/WorkerOptimizer/'+asset)
        entries=tools.call_method('GetWidgets',args=(blueprint,)).widgets
        return next(entry.widget for entry in entries if str(entry.widget_name)==name)
    panel=widget('WBP_SettingsPanel','PanelRoot')
    shadow=widget('WBP_WorkerOptimizer','PanelShadow')
    for brush,name,margin in ((panel.get_editor_property('background'),'T_WorkerOptimizerFrame',6/16),
                              (shadow.get_editor_property('brush'),'T_WorkerOptimizerShadow',24/64)):
        assert brush.get_editor_property('resource_object')==unreal.load_asset('/Game/Mods/WorkerOptimizer/'+name)
        assert brush.get_editor_property('draw_as')==unreal.SlateBrushDrawType.BOX
        actual=brush.get_editor_property('margin')
        assert all(abs(getattr(actual,edge)-margin)<1e-6 for edge in ('left','top','right','bottom'))
    tint=shadow.get_editor_property('color_and_opacity')
    assert tint.r==tint.g==tint.b==0 and abs(tint.a-0.45)<1e-6
    assert shadow.get_visibility()==unreal.SlateVisibility.COLLAPSED
    assert shadow.slot.get_z_order()<widget('WBP_WorkerOptimizer','PanelScale').slot.get_z_order()
    unreal.log('WO_UI_FRAME_WIDGETS_PASS: panel frame resource, non-interactive black45percent shadow and behind-panel order')

def run_native_icons():
    import unreal
    from ui_authoring import color, declare, text
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP
    root='/Game/Mods/WorkerOptimizer/'
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    factory=unreal.get_default_object(unreal.load_class(None,'/Script/UMG.WidgetBlueprintLibrary'))
    row=factory.call_method('Create',args=(world,unreal.load_class(None,root+'WBP_HistoryRow.WBP_HistoryRow_C'),None))
    item_class=unreal.load_class(None,root+'BP_UIListItem.BP_UIListItem_C')
    fixture=BP.create('/Game/WorkerOptimizerEditorTests','BP_StatusIconInputs',unreal.Object.static_class())
    graphs=declare(fixture,{}, {'Populate':([('Item',item_class),('Status','name')],[])})
    BP.write_graph_dsl(graphs['Populate'],'(fn Populate (Item Status) (Class|BPUIListItem|SetStatus :self Item :Status Status) (Class|BPUIListItem|SetTitle :self Item :Title '+text('"Fixture outcome"')+'))')
    BP.compile_blueprint(fixture,warnings_as_errors=True)
    inputs=unreal.new_object(fixture.generated_class())
    for status,key in (('completed','ok'),('problems','warn'),('error','err'),('aborted','abort')):
        item=unreal.new_object(item_class)
        inputs.call_method('Populate',args=(item,status))
        assert row.call_method('SetItem',args=(item,))
        icon=row.get_editor_property('StatusIcon')
        assert icon.get_visibility()==unreal.SlateVisibility.HIT_TEST_INVISIBLE
        assert icon.get_editor_property('brush').get_editor_property('resource_object')==unreal.load_asset(root+STATUS_ASSETS[status])
        actual=icon.get_editor_property('color_and_opacity')
        expected=color(key)
        assert all(abs(getattr(actual,c)-getattr(expected,c))<1e-6 for c in ('r','g','b'))
        assert row.get_editor_property('StatusTextCell').get_visibility()==unreal.SlateVisibility.COLLAPSED
    assert not row.call_method('SetItem',args=(None,))
    assert row.get_editor_property('StatusIcon').get_visibility()==unreal.SlateVisibility.COLLAPSED
    hud=factory.call_method('Create',args=(world,unreal.load_class(None,root+'WBP_WorkerOptimizer.WBP_WorkerOptimizer_C'),None))
    assert isinstance(hud.get_editor_property('OutcomeIcon'),unreal.Image)
    assert hud.get_editor_property('OutcomeBadge').get_visibility()==unreal.SlateVisibility.COLLAPSED
    unreal.log('WO_UI_STATUS_ICONS_NATIVE_PASS: four texture/tint states, localized-title companion, recycled-invalid reset and no visible font glyph dependency')

if __name__=='__main__':
    run_source()
    if 'unreal' in sys.modules:
        validate_assets()
        run_native_frames()
        run_native_icons()
