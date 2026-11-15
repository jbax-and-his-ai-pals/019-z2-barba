-- Palace 6 Lava Link: fireball-only kill (no thrust techniques), key drop, scroll unlock and exit.
-- (tests/link_boss.lua covers his art, palette, beams and hurt sound.)
dofile(TEST_DIR..'/boss_fight.lua')
runBossFight{name='lava_link_kill',world=4,region=2,number=6,room=0x3A,page=1,kind=4,p56C=1,
    bosses={[0x21]=true},final=0x21,attack=7,frames=12000,exitPage=2,
    checks=function(check,fight)
        check((fight.damage[0x21] or 0)>0,'fireballs damaged Lava Link ($21)')
    end}
