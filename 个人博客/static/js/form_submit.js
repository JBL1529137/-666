// 表单提交辅助函数
document.addEventListener('DOMContentLoaded', function() {
    console.log('表单提交脚本已加载');
    
    // 获取表单
    var noteForm = document.getElementById('note-form');
    if (noteForm) {
        console.log('找到笔记表单');
        
        // 监听表单提交
        noteForm.addEventListener('submit', function(e) {
            console.log('表单正在提交...');
        });
        
        // 监听提交按钮点击
        var submitButton = document.querySelector('button[type="submit"]');
        if (submitButton) {
            console.log('找到提交按钮');
            submitButton.addEventListener('click', function(e) {
                console.log('提交按钮被点击');
            });
        }
    }
    
    // Ctrl+S 快捷键
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 's' && noteForm) {
            e.preventDefault();
            console.log('Ctrl+S 快捷键触发提交');
            
            // 确保表单有效
            if (noteForm.checkValidity()) {
                console.log('表单验证通过，提交中...');
                noteForm.submit();
            } else {
                console.log('表单验证失败');
                noteForm.reportValidity();
            }
        }
    });
});

// 手动提交表单的函数
function submitNoteForm() {
    console.log('调用手动提交表单函数');
    var form = document.getElementById('note-form');
    if (form) {
        if (form.checkValidity()) {
            console.log('表单验证通过，手动提交中...');
            form.submit();
        } else {
            console.log('表单验证失败');
            form.reportValidity();
        }
    } else {
        console.error('找不到表单元素');
    }
} 