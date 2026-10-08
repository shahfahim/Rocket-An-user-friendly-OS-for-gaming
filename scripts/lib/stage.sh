# Helpers for staging the archiso profile before mkarchiso. Source this file.

# apply_symlinks <spec-file> <root>
# Each non-comment line of <spec-file> is "<path relative to root> -> <target>".
apply_symlinks() {
    local spec=$1 root=$2 line link target
    while IFS= read -r line || [[ -n $line ]]; do
        [[ -z ${line// } || $line == \#* ]] && continue
        if [[ $line != *" -> "* ]]; then
            echo "ERROR: malformed symlink line: '$line'" >&2
            return 1
        fi
        link=${line%% -> *}
        target=${line#* -> }
        mkdir -p "$root/$(dirname "$link")"
        ln -sfn "$target" "$root/$link"
    done < "$spec"
}

# swap_kernel <profile-dir> <from> <to>
# Replaces kernel package names and boot entry file names, e.g. linux-cachyos -> linux-zen.
swap_kernel() {
    local profile=$1 from=$2 to=$3
    sed -i -E "s/^${from}(-headers)?$/${to}\1/" "$profile/packages.x86_64"
    if [[ -d $profile/efiboot/loader/entries ]]; then
        sed -i "s/-${from#linux-}\b/-${to#linux-}/g" "$profile"/efiboot/loader/entries/*.conf
    fi
}

# make_branding_images <dir>
# Generates logo.png (256x256) and welcome.png (800x300) so no binary assets live in git.
make_branding_images() {
    local dir=$1 bg='#121418' fg='#FF6A00'
    mkdir -p "$dir"
    magick -size 256x256 "xc:$bg" -fill "$fg" \
        -draw "polygon 128,24 168,120 168,196 88,196 88,120" \
        -draw "polygon 88,150 52,210 88,196" -draw "polygon 168,150 204,210 168,196" \
        -fill "$bg" -draw "circle 128,110 128,128" "PNG32:$dir/logo.png"
    magick -size 800x300 "xc:$bg" -fill "$fg" -gravity center -font DejaVu-Sans-Bold -pointsize 72 \
        -annotate +0-20 "Rocket OS" -fill '#FFFFFF' -font DejaVu-Sans -pointsize 24 \
        -annotate +0+50 "Built for gaming" "PNG32:$dir/welcome.png"
}
