-- Numeric room evidence shared by capture and reload; never modifies game RAM.
function checkpointFeature(spec)
    local function r(a)return emu.read(a,emu.memType.nesMemory)end
    local x,y=r(0x3B)*256+r(0x4D),r(0x29)
    local function tile(px,py)
        return r(0x6000+math.floor(px/256)*208+math.floor(py/16)*16+math.floor(px%256/16))
    end
    local detail=string.format('world=%d room=$%02X x=%d y=%d',r(0x707),r(0x561),x,y)
    if spec.feature=='elevator' then
        for slot=0,5 do
            if r(0xA1+slot)==0x13 and r(0xB6+slot)==1 then
                local ex=r(0x3C+slot)*256+r(0x4E+slot)
                local ey=r(0x2A+slot)
                return r(0x754)~=0 and y==ey+8 and math.abs(x-ex)<=12,
                    detail..string.format(' elevator slot=%d id=$13 x=%d y=%d in=$%02X',slot,ex,ey,r(0x754))
            end
        end
        return false,detail..' missing elevator'
    elseif spec.feature=='ceiling' then
        local head,body,floor=tile(x+4,y-48),tile(x+4,y-16),tile(x+4,y)
        return head==0x4C and body==0x42 and (floor==0x4B or floor==0x4C) and (r(0x5F6)&2)~=0,
            detail..string.format(' ceiling=$%02X body=$%02X floor=$%02X fold=%d',head,body,floor,r(0x5F6))
    elseif spec.feature=='pit' then
        local edge=math.floor((x+4)/16)*16+16
        local values={};local empty=true
        for py=y,192,16 do
            local value=tile(edge,py);values[#values+1]=string.format('%02X',value)
            if value~=0x40 and value~=0x42 then empty=false end
        end
        local floor=tile(x+4,y)
        return (floor==0x4B or floor==0x4C) and empty and r(0x479)==0,
            detail..string.format(' support=$%02X next-column-x=%d tiles=%s grounded=%d',floor,edge,table.concat(values,','),r(0x479))
    end
    return true,detail
end
