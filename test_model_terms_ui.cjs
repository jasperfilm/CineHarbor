const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function fixture(locale) {
  const nodes = new Map();
  const calls = [];
  const notice = {
    id: 'minimax-h3', name: 'MiniMax H3',
    links: [{title: 'H3 License', url: '/licenses/models/MiniMax-H3-LICENSE.txt'}]
  };
  function node(tag) {
    return {
      tag, children: [], append(...items) { this.children.push(...items); },
      setAttribute() {}, addEventListener(name, listener) { this.listeners[name] = listener; },
      listeners: {},
      showModal() { nodes.set(this.id, this); }, close() { this.listeners.close(); },
      remove() { nodes.delete(this.id); }
    };
  }
  const button = node('button');
  nodes.set('review-model-terms', button);
  nodes.set('model', {value: 'h3'});
  const context = {
    window: {}, L: {locale}, esc: value => value,
    UI: {shotFooterActions: [], binders: []},
    action: run => run(), api: async path => { calls.push(path); return notice; },
    document: {
      body: node('body'), getElementById: id => nodes.get(id), createElement: node
    }
  };
  vm.createContext(context);
  for (const file of ['model-terms-copy.js', 'model-terms.js']) {
    vm.runInContext(fs.readFileSync(`${__dirname}/web/${file}`, 'utf8'), context);
  }
  context.UI.binders[0]();
  return {button, nodes, calls, notice, context};
}

(async () => {
  for (const locale of ['en', 'zh-Hans', 'zh-Hant', 'ja', 'ko', 'unsupported']) {
    const {button, nodes, calls, notice, context} = fixture(locale);
    const copy = context.window.CineHarborModelTermsCopy[locale] || context.window.CineHarborModelTermsCopy.en;
    assert.match(context.UI.shotFooterActions[0](), /model-terms\.html/);
    assert.deepEqual(calls, []);
    await button.onclick();
    const dialog = nodes.get('model-terms-dialog');
    assert.equal(dialog.children[0].textContent, copy.title);
    assert.equal(dialog.children.find(child => child.tag === 'h3').textContent, 'MiniMax H3');
    const source = dialog.children.flatMap(child => child.children).find(child => child.tag === 'a');
    assert.equal(source.href, notice.links[0].url);
    assert.deepEqual(dialog.children.filter(child => child.tag === 'input'), []);
    const buttons = dialog.children.filter(child => child.tag === 'button');
    assert.equal(buttons.length, 1);
    assert.equal(buttons[0].textContent, copy.close);
    assert.ok(!buttons[0].disabled);
    buttons[0].onclick();
    assert.ok(!nodes.has('model-terms-dialog'));
    assert.deepEqual(calls, ['/api/model-terms']);
  }
  console.log('Optional model notice opens on request, preserves the license link, and closes without acknowledgement in all locales.');
})().catch(error => { console.error(error); process.exitCode = 1; });
